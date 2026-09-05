"""
Limited source-to-sink data-flow analysis for CWE-89 (SQL Injection) and
CWE-295 (Improper Certificate Validation).

Scope (deliberately limited, per project requirements - this is NOT a
full-program static analyzer):
  - Single-file, statement-per-line analysis (matches how the rest of the
    system already reports detections by line number).
  - Intraprocedural taint tracking through variable assignment and string
    concatenation.
  - One bounded interprocedural hop: a tainted value passed as an argument
    into another method defined in the SAME file is tracked into that
    method's parameters too. No cross-file, no reflection, no call-graph
    beyond that single hop.
  - Certificate-validation checks are structural (inspect the actual body
    of HostnameVerifier/X509TrustManager/onReceivedSslError
    implementations) rather than a whole-file keyword search, so a custom
    implementation that genuinely validates isn't blanket-flagged.
"""

import re

# =====================================================
# Shared helpers
# =====================================================

def _find_matching_paren(text: str, open_idx: int) -> int:
    """Given the index of a '(' , return the index of its matching ')'."""
    depth = 0
    i = open_idx
    in_str = False
    str_char = ''
    while i < len(text):
        c = text[i]
        if in_str:
            if c == '\\':
                i += 2
                continue
            if c == str_char:
                in_str = False
        else:
            if c in ('"', "'"):
                in_str = True
                str_char = c
            elif c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return len(text) - 1


def _find_matching_brace(text: str, open_idx: int) -> int:
    """Given the index of a '{', return the index of its matching '}'."""
    depth = 0
    i = open_idx
    in_str = False
    str_char = ''
    while i < len(text):
        c = text[i]
        if in_str:
            if c == '\\':
                i += 2
                continue
            if c == str_char:
                in_str = False
        else:
            if c in ('"', "'"):
                in_str = True
                str_char = c
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return len(text) - 1


def _split_top_level_args(arg_text: str) -> list:
    """Split a call's argument text on top-level commas (ignoring commas
    inside nested parens/brackets/quotes)."""
    args = []
    depth = 0
    in_str = False
    str_char = ''
    current = []
    i = 0
    while i < len(arg_text):
        c = arg_text[i]
        if in_str:
            current.append(c)
            if c == '\\':
                i += 1
                if i < len(arg_text):
                    current.append(arg_text[i])
            elif c == str_char:
                in_str = False
        else:
            if c in ('"', "'"):
                in_str = True
                str_char = c
                current.append(c)
            elif c in '([{':
                depth += 1
                current.append(c)
            elif c in ')]}':
                depth -= 1
                current.append(c)
            elif c == ',' and depth == 0:
                args.append(''.join(current).strip())
                current = []
            else:
                current.append(c)
        i += 1
    if current:
        args.append(''.join(current).strip())
    return [a for a in args if a != '']


SINK_CALL_LOOKAHEAD_LINES = 6


def _extract_sink_args(lines, start_idx: int, match_start_in_line: int):
    """
    A sink call's arguments commonly span multiple lines (e.g. the
    canonical parameterized-query style:
        db.rawQuery(
            "SELECT ... WHERE id=?",
            new String[]{userId}
        );
    ). Joins a bounded lookahead window of subsequent lines so the
    balanced-paren argument parser can see the whole call, not just the
    line the sink name appeared on. Returns (args, extra_lines_consumed)
    or (None, 0) if no balanced call was found in the window.
    """
    window = lines[start_idx:start_idx + SINK_CALL_LOOKAHEAD_LINES]
    joined = '\n'.join(window)
    open_idx = joined.find('(', match_start_in_line)
    if open_idx == -1:
        return None, 0
    close_idx = _find_matching_paren(joined, open_idx)
    args = _split_top_level_args(joined[open_idx + 1:close_idx])
    if not args:
        return None, 0
    extra_lines_consumed = joined[:close_idx].count('\n')
    return args, extra_lines_consumed


def _strip_quoted_strings(expr: str) -> str:
    """Replace the contents of string literals with a placeholder so
    concatenation/identifier checks aren't confused by text inside
    quotes (e.g. a literal containing the word '+' or a variable name)."""
    return re.sub(r'"(?:[^"\\]|\\.)*"', '""', expr)


def _has_placeholder(expr: str) -> bool:
    """True if a quoted string in expr contains a '?' SQL placeholder."""
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', expr):
        if '?' in m.group(1):
            return True
    return False


def _has_concatenation(expr: str) -> bool:
    stripped = _strip_quoted_strings(expr)
    return '+' in stripped or '.plus(' in stripped or re.search(r'\bconcat\s*\(', stripped, re.I) is not None


ASSIGN_RE = re.compile(
    r'^\s*(?:val\s+|var\s+|final\s+)?(?:[\w\.\<\>\[\],\?]+\s+)?([A-Za-z_]\w*)\s*=\s*([^=;].*?);?\s*$'
)

IDENTIFIER_RE = re.compile(r'\b[A-Za-z_]\w*\b')

RESERVED_WORDS = {
    'if', 'else', 'for', 'while', 'return', 'new', 'null', 'true', 'false',
    'this', 'super', 'try', 'catch', 'finally', 'val', 'var', 'fun', 'class',
    'public', 'private', 'protected', 'static', 'final', 'void', 'int',
    'String', 'boolean', 'throw', 'throws', 'import', 'package'
}


def _identifiers_in(expr: str) -> set:
    stripped = _strip_quoted_strings(expr)
    return {tok for tok in IDENTIFIER_RE.findall(stripped) if tok not in RESERVED_WORDS}


# =====================================================
# SQL Injection (CWE-89) source-to-sink analysis
# =====================================================

SQL_SOURCES = [
    (re.compile(r'\.getStringExtra\s*\('), 'Intent.getStringExtra()'),
    (re.compile(r'\.getQueryParameter\s*\('), 'Uri.getQueryParameter()'),
    (re.compile(r'\.getExtras\s*\(\s*\)'), 'Intent.getExtras()'),
    (re.compile(r'\.getText\s*\(\s*\)\s*\.toString\s*\(\s*\)'), 'EditText.getText().toString()'),
    (re.compile(r'\.getText\s*\(\s*\)'), 'EditText.getText()'),
]
# Bundle.getString(...) needs its own pattern since plain .getString( is common noise
BUNDLE_SOURCE_RE = re.compile(r'\bBundle\b')

SQL_SINK_NAMES = [
    (re.compile(r'\.rawQuery\s*\('), 'rawQuery()'),
    (re.compile(r'\.execSQL\s*\('), 'execSQL()'),
    (re.compile(r'\.compileStatement\s*\('), 'compileStatement()'),
    (re.compile(r'\bSimpleSQLiteQuery\s*\('), 'SimpleSQLiteQuery() (Room @RawQuery)'),
]

METHOD_SIG_RE = re.compile(
    r'(?:fun\s+(\w+)\s*\(([^)]*)\)|(?:public|private|protected|internal)?\s*(?:static\s+)?[\w<>\[\]\.]+\s+(\w+)\s*\(([^)]*)\))\s*[:{]?'
)

PARAM_SPLIT_RE = re.compile(r',(?![^<]*>)')


def _extract_methods(code: str):
    """Very light method-boundary extraction: name -> (param_names, body_start, body_end)."""
    methods = {}
    for m in re.finditer(r'\b(?:fun\s+(\w+)|(?:\w+)\s+(\w+))\s*\(([^)]*)\)\s*(?:[:\w<>\[\]\.\s]*)?\{', code):
        name = m.group(1) or m.group(2)
        if name is None or name in RESERVED_WORDS:
            continue
        params_raw = m.group(3)
        param_names = []
        if params_raw.strip():
            for p in PARAM_SPLIT_RE.split(params_raw):
                p = p.strip()
                if not p:
                    continue
                # Kotlin: "name: Type"   Java: "Type name"
                if ':' in p:
                    param_names.append(p.split(':')[0].strip())
                else:
                    parts = p.split()
                    if parts:
                        param_names.append(parts[-1].strip('*'))
        brace_idx = code.rfind('{', 0, m.end())
        if brace_idx == -1:
            continue
        end_idx = _find_matching_brace(code, brace_idx)
        methods[name] = {
            'params': param_names,
            'start': brace_idx,
            'end': end_idx,
        }
    return methods


def analyze_sql_dataflow(code: str) -> list:
    """
    Returns a list of source-to-sink findings for SQL Injection:
    [{
        "line": int, "sink": str, "tainted_expression": str,
        "path": [str, ...], "explanation": str, "detection_basis": str
    }, ...]
    """
    findings = []
    lines = code.splitlines()

    # taint[varname] = {"path": [...], "kind": "traced"|"unparameterized"}
    taint = {}
    methods = _extract_methods(code)
    method_param_taint = {}  # method_name -> {param_name: path}

    for idx, line in enumerate(lines):
        stripped_for_scan = _strip_quoted_strings(line)

        # ---- Source detection ----
        found_source_kind = None
        for pattern, kind in SQL_SOURCES:
            if pattern.search(line):
                found_source_kind = kind
                break
        if found_source_kind is None and BUNDLE_SOURCE_RE.search(line) and '.getString(' in line:
            found_source_kind = 'Bundle.getString()'

        # ---- Assignment / taint propagation ----
        assign_match = ASSIGN_RE.match(line)
        if assign_match:
            var_name, rhs = assign_match.group(1), assign_match.group(2)
            rhs_ids = _identifiers_in(rhs)

            if found_source_kind:
                taint[var_name] = {
                    'path': [found_source_kind, f'{var_name} (line {idx})'],
                    'basis': 'traced-source',
                }
            else:
                # propagate taint from any tainted identifier used on the RHS
                contributing = [v for v in rhs_ids if v in taint]
                if contributing:
                    # merge paths (use the first contributor's path, note others)
                    base_path = list(taint[contributing[0]]['path'])
                    base_path.append(f'{var_name} (line {idx})')
                    taint[var_name] = {'path': base_path, 'basis': taint[contributing[0]]['basis']}
                elif _has_concatenation(rhs):
                    # Built via concatenation with something we can't trace to a
                    # named source (e.g. a bare method parameter) - still an
                    # unparameterized-construction finding once it reaches a sink.
                    taint[var_name] = {
                        'path': ['(unconfirmed external input)', f'{var_name} built via concatenation (line {idx})'],
                        'basis': 'unparameterized-concatenation',
                    }

        # ---- One-hop interprocedural: tainted arg passed into a same-file method ----
        call_match = re.search(r'\b(\w+)\s*\(', line)
        if call_match and call_match.group(1) in methods and call_match.group(1) not in RESERVED_WORDS:
            callee = call_match.group(1)
            open_idx = line.find('(', call_match.start())
            if open_idx != -1:
                close_idx = _find_matching_paren(line, open_idx)
                call_args = _split_top_level_args(line[open_idx + 1:close_idx])
                param_names = methods[callee]['params']
                for i, arg_expr in enumerate(call_args):
                    if i >= len(param_names):
                        break
                    arg_ids = _identifiers_in(arg_expr)
                    tainted_arg_ids = [a for a in arg_ids if a in taint]
                    if tainted_arg_ids:
                        path = list(taint[tainted_arg_ids[0]]['path'])
                        path.append(f'{param_names[i]} (parameter of {callee}())')
                        method_param_taint.setdefault(callee, {})[param_names[i]] = path

        # ---- Sink detection ----
        for pattern, sink_name in SQL_SINK_NAMES:
            sink_match = pattern.search(line)
            if not sink_match:
                continue

            args, _ = _extract_sink_args(lines, idx, sink_match.start())
            if args is None:
                continue

            query_arg = args[0]
            has_concat = _has_concatenation(query_arg)
            query_is_pure_literal = bool(re.match(r'^\s*"(?:[^"\\]|\\.)*"\s*$', query_arg))
            placeholder_only = query_is_pure_literal and _has_placeholder(query_arg)

            if placeholder_only:
                # Properly parameterized literal - safe regardless of args[1].
                continue

            query_ids = _identifiers_in(query_arg)
            traced_ids = [v for v in query_ids if v in taint]

            is_vulnerable = False
            explanation = None
            path = []
            basis = None

            if traced_ids:
                taint_entry = taint[traced_ids[0]]
                path = list(taint_entry['path'])
                path.append(f'{sink_name}')
                is_vulnerable = True
                basis = taint_entry['basis']
                if basis == 'traced-source':
                    explanation = (
                        f"User-controlled data from {path[0]} reaches SQL execution sink "
                        f"'{sink_name}' via variable '{traced_ids[0]}' without safe parameterization."
                    )
                else:
                    explanation = (
                        f"Variable '{traced_ids[0]}' is built via string concatenation and reaches "
                        f"SQL execution sink '{sink_name}' without a parameterized placeholder ('?') "
                        "and selectionArgs."
                    )
            elif has_concat and not query_is_pure_literal:
                # Direct string concatenation feeding straight into the sink,
                # source not traced but the unsafe construction pattern itself
                # is the finding (matches the "missing parameterization" /
                # "string concatenation" categories).
                is_vulnerable = True
                basis = 'unparameterized-concatenation'
                path = ['(unconfirmed external input)', 'string concatenation', sink_name]
                explanation = (
                    f"Query string passed to '{sink_name}' is built via string concatenation "
                    "instead of a parameterized placeholder ('?') with selectionArgs."
                )

            if is_vulnerable:
                findings.append({
                    'line': idx,
                    'code': line.strip(),
                    'sink': sink_name,
                    'tainted_variable': traced_ids[0] if traced_ids else None,
                    'path': path,
                    'explanation': explanation,
                    'detection_basis': basis,
                })

    # Second pass: check same-file callee method bodies for sinks reached by
    # tainted parameters propagated from the one-hop interprocedural step above.
    for callee, param_taints in method_param_taint.items():
        body_start, body_end = methods[callee]['start'], methods[callee]['end']
        body_text = code[body_start:body_end + 1]
        body_lines = body_text.splitlines()
        base_line_offset = code[:body_start].count('\n')

        for b_idx, b_line in enumerate(body_lines):
            for pattern, sink_name in SQL_SINK_NAMES:
                sink_match = pattern.search(b_line)
                if not sink_match:
                    continue
                args, _ = _extract_sink_args(body_lines, b_idx, sink_match.start())
                if args is None:
                    continue
                query_arg = args[0]
                query_ids = _identifiers_in(query_arg)
                for pname, ppath in param_taints.items():
                    if pname in query_ids:
                        full_path = list(ppath) + [sink_name]
                        findings.append({
                            'line': base_line_offset + b_idx,
                            'code': b_line.strip(),
                            'sink': sink_name,
                            'tainted_variable': pname,
                            'path': full_path,
                            'explanation': (
                                f"User-controlled data from {full_path[0]} reaches SQL execution "
                                f"sink '{sink_name}' inside {callee}() via parameter '{pname}', "
                                "passed in from the caller, without safe parameterization."
                            ),
                            'detection_basis': 'traced-source-interprocedural',
                        })

    return findings


def sql_sink_safety_summary(code: str) -> dict:
    """
    Inspects every SQL sink call in the code and reports whether ALL of
    them use a clean parameterized literal ('?' placeholder, no
    concatenation). Used as a suppression signal for the ML/keyword
    layer: a snippet whose only sink calls are properly parameterized
    shouldn't be overridden into "vulnerable" by a coincidental
    substring match elsewhere in the model's feature set.

    Returns {"sinks_found": int, "all_parameterized": bool}.
    "all_parameterized" is only meaningful when sinks_found > 0.
    """
    sinks_found = 0
    all_safe = True
    lines = code.splitlines()
    for idx, line in enumerate(lines):
        for pattern, sink_name in SQL_SINK_NAMES:
            sink_match = pattern.search(line)
            if not sink_match:
                continue
            args, _ = _extract_sink_args(lines, idx, sink_match.start())
            if args is None:
                continue
            sinks_found += 1
            query_arg = args[0]
            query_is_pure_literal = bool(re.match(r'^\s*"(?:[^"\\]|\\.)*"\s*$', query_arg))
            if not (query_is_pure_literal and _has_placeholder(query_arg)):
                all_safe = False
    return {'sinks_found': sinks_found, 'all_parameterized': all_safe if sinks_found else False}


# =====================================================
# Certificate Validation (CWE-295) structural analysis
# =====================================================

def _extract_named_blocks(code: str, class_or_impl_pattern: re.Pattern):
    """Find blocks (class bodies / anonymous object bodies) matching a
    pattern, returning their (start, end) brace-balanced span."""
    blocks = []
    for m in class_or_impl_pattern.finditer(code):
        brace_idx = code.find('{', m.end())
        if brace_idx == -1:
            continue
        end_idx = _find_matching_brace(code, brace_idx)
        blocks.append((m.start(), brace_idx, end_idx))
    return blocks


def _extract_method_body(block_text: str, method_name: str):
    m = re.search(r'\b' + method_name + r'\s*\([^)]*\)[^{]*\{', block_text)
    if not m:
        return None
    open_idx = block_text.rfind('{', 0, m.end())
    end_idx = _find_matching_brace(block_text, open_idx)
    return block_text[open_idx + 1:end_idx]


def _line_of(code: str, char_idx: int) -> int:
    return code[:char_idx].count('\n')


# A leading dotted package prefix (e.g. "implements javax.net.ssl.X509TrustManager",
# the form javac requires when the interface isn't separately imported) is
# optional in every branch below - a bare, unqualified reference matches
# exactly as before. Without this, real Android code that doesn't import
# the interface by simple name was silently invisible to this analyzer
# (falling through to no finding at all, neither SAFE nor VULNERABLE).
_QUALIFIED_HOSTNAME_VERIFIER = r'(?:[\w.]+\.)?HostnameVerifier'
_QUALIFIED_TRUST_MANAGER = r'(?:[\w.]+\.)?X509TrustManager'
HOSTNAME_VERIFIER_RE = re.compile(
    r'(?:class\s+\w+\s*[:(].*?\b' + _QUALIFIED_HOSTNAME_VERIFIER + r'\b'
    r'|:\s*' + _QUALIFIED_HOSTNAME_VERIFIER + r'\b'
    r'|new\s+' + _QUALIFIED_HOSTNAME_VERIFIER + r'\s*\(\s*\)'
    r'|implements\s+' + _QUALIFIED_HOSTNAME_VERIFIER + r'\b)'
)
TRUST_MANAGER_RE = re.compile(
    r'(?:class\s+\w+\s*[:(].*?\b' + _QUALIFIED_TRUST_MANAGER + r'\b'
    r'|:\s*' + _QUALIFIED_TRUST_MANAGER + r'\b'
    r'|new\s+' + _QUALIFIED_TRUST_MANAGER + r'\s*\(\s*\)'
    r'|implements\s+' + _QUALIFIED_TRUST_MANAGER + r'\b)'
)
SSL_ERROR_HANDLER_RE = re.compile(r'\bonReceivedSslError\s*\([^)]*\)')


def analyze_cert_dataflow(code: str) -> list:
    """
    Returns a list of certificate-validation findings, each classified
    SAFE / SUSPICIOUS / VULNERABLE based on inspecting the actual body of
    the relevant method (not just a whole-file keyword search).
    [{
        "line": int, "component": str, "verdict": "VULNERABLE"|"SUSPICIOUS"|"SAFE",
        "path": [...], "explanation": str
    }, ...]
    """
    findings = []

    # ---- HostnameVerifier.verify() ----
    for start, brace_idx, end_idx in _extract_named_blocks(code, HOSTNAME_VERIFIER_RE):
        block_text = code[brace_idx:end_idx + 1]
        body = _extract_method_body(block_text, 'verify')
        if body is None:
            continue
        body_stripped = _strip_quoted_strings(body).strip()
        real_statements = [s.strip() for s in body_stripped.split(';') if s.strip() and not s.strip().startswith('//')]

        if re.fullmatch(r'return\s+true', real_statements[-1]) if real_statements else False:
            if len(real_statements) == 1:
                verdict, explanation = 'VULNERABLE', (
                    "HostnameVerifier.verify() unconditionally returns true - "
                    "hostname checking is disabled, any certificate hostname is accepted."
                )
            else:
                verdict, explanation = 'SUSPICIOUS', (
                    "HostnameVerifier.verify() has other logic but its final return is an "
                    "unconditional 'true' - review whether the preceding checks can actually reject a mismatch."
                )
        elif re.search(r'HttpsURLConnection\.getDefaultHostnameVerifier|\.verify\s*\(', body_stripped):
            verdict, explanation = 'SAFE', (
                "HostnameVerifier.verify() delegates to a real hostname check "
                "(default verifier or an explicit comparison) rather than always accepting."
            )
        else:
            verdict, explanation = 'SUSPICIOUS', (
                "Custom HostnameVerifier.verify() implementation found - could not confirm it "
                "performs a real hostname comparison; manual review recommended."
            )

        findings.append({
            'line': _line_of(code, start),
            'component': 'HostnameVerifier',
            'verdict': verdict,
            'path': ['Network connection', 'HostnameVerifier.verify()', 'Trust decision'],
            'explanation': explanation,
        })

    # ---- X509TrustManager.checkServerTrusted / checkClientTrusted ----
    for start, brace_idx, end_idx in _extract_named_blocks(code, TRUST_MANAGER_RE):
        block_text = code[brace_idx:end_idx + 1]
        for method_name in ('checkServerTrusted', 'checkClientTrusted'):
            body = _extract_method_body(block_text, method_name)
            if body is None:
                continue
            body_stripped = _strip_quoted_strings(body).strip()
            real_statements = [s.strip() for s in body_stripped.split(';') if s.strip() and not s.strip().startswith('//')]

            if not real_statements:
                verdict, explanation = 'VULNERABLE', (
                    f"{method_name}() has an empty body - it accepts every certificate chain "
                    "without validation."
                )
            elif re.search(r'\bthrow\b|\bCertificateException\b', body_stripped):
                verdict, explanation = 'SAFE', (
                    f"{method_name}() can throw a CertificateException, indicating it actually "
                    "validates the chain instead of accepting everything."
                )
            elif re.search(r'\bdefaultTrustManager\b|X509TrustManagerImpl|TrustManagerFactory', body_stripped):
                verdict, explanation = 'SAFE', (
                    f"{method_name}() delegates to a real trust manager/factory."
                )
            else:
                verdict, explanation = 'SUSPICIOUS', (
                    f"{method_name}() has a non-empty body but no visible throw/validation call - "
                    "manual review recommended."
                )

            findings.append({
                'line': _line_of(code, brace_idx) + body[:0].count('\n'),
                'component': f'X509TrustManager.{method_name}',
                'verdict': verdict,
                'path': ['Network connection', f'X509TrustManager.{method_name}()', 'Trust decision'],
                'explanation': explanation,
            })

    # ---- WebViewClient.onReceivedSslError ----
    for m in SSL_ERROR_HANDLER_RE.finditer(code):
        brace_idx = code.find('{', m.end())
        if brace_idx == -1:
            continue
        end_idx = _find_matching_brace(code, brace_idx)
        body = code[brace_idx + 1:end_idx]
        body_stripped = _strip_quoted_strings(body)

        calls_proceed = re.search(r'\bhandler\s*\.\s*proceed\s*\(\s*\)', body_stripped)
        calls_cancel = re.search(r'\bhandler\s*\.\s*cancel\s*\(\s*\)', body_stripped)
        is_conditional = bool(re.search(r'\bif\s*\(', body_stripped))

        if calls_proceed and not is_conditional:
            verdict, explanation = 'VULNERABLE', (
                "onReceivedSslError() calls handler.proceed() unconditionally - SSL errors "
                "(e.g. expired/invalid/self-signed certificates) are always ignored."
            )
        elif calls_proceed and is_conditional:
            verdict, explanation = 'SUSPICIOUS', (
                "onReceivedSslError() calls handler.proceed() conditionally - verify the "
                "condition doesn't effectively allow all errors through."
            )
        elif calls_cancel:
            verdict, explanation = 'SAFE', (
                "onReceivedSslError() calls handler.cancel(), rejecting the connection on SSL error."
            )
        else:
            verdict, explanation = 'SUSPICIOUS', (
                "onReceivedSslError() implementation found but no clear proceed()/cancel() call detected."
            )

        findings.append({
            'line': _line_of(code, m.start()),
            'component': 'WebViewClient.onReceivedSslError',
            'verdict': verdict,
            'path': ['SSL error', 'onReceivedSslError()', 'handler.proceed()/cancel()'],
            'explanation': explanation,
        })

    return findings
