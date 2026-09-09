import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exceptions.dart';
import '../models/apk_scan_result_model.dart';
import '../repositories/apps_repository.dart';
import '../routing/app_router.dart';
import '../theme/app_colors.dart';
import '../widgets/risk_badge.dart';
import '../widgets/state_views.dart';

/// Flutter APK Scan implementation phase: replaces the previous
/// intentional NotAvailableScreen stub for "Upload APK" now that the
/// backend genuinely performs CWE-89/CWE-295 analysis on an uploaded APK
/// (see backend/apk_code_scanner.py). Every value shown here is exactly
/// what POST /upload-apk returned - no fabricated finding, no invented
/// line number, no client-side re-scoring.
class ApkScanScreen extends StatefulWidget {
  const ApkScanScreen({super.key});

  @override
  State<ApkScanScreen> createState() => _ApkScanScreenState();
}

enum _Stage { pick, uploading, result, error }

class _ApkScanScreenState extends State<ApkScanScreen> {
  _Stage _stage = _Stage.pick;
  PlatformFile? _selectedFile;
  ApkScanResult? _result;
  String? _errorMessage;

  Future<void> _pickFile() async {
    // withData: true (removed) used to make the native file_picker plugin
    // read the WHOLE file on the Android side and ship it back to Dart as
    // one giant byte array inside a single platform-channel result
    // envelope - fine for a small test file, but a real-world APK (tens to
    // hundreds of MB) blows past the app's default JVM heap trying to
    // allocate that one contiguous buffer, crashing the entire process
    // with a native OutOfMemoryError (reproduced live: a 184MB APK failed
    // to allocate a ~193MB buffer against a ~201MB heap cap, in
    // StandardMessageCodec.writeBytes - never even reaching Dart code).
    // Only the file's path is requested now; the bytes are read
    // separately, directly from disk, in _startScan() below.
    try {
      final picked = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['apk'],
      );
      if (picked == null || picked.files.isEmpty) {
        // User cancelled the picker - stay exactly where we were, no error.
        return;
      }
      final file = picked.files.single;
      if (!file.name.toLowerCase().endsWith('.apk') || file.path == null) {
        setState(() {
          _stage = _Stage.error;
          _errorMessage = 'That file is not an APK. Please select a real .apk file.';
        });
        return;
      }
      setState(() {
        _selectedFile = file;
        _stage = _Stage.pick;
        _result = null;
        _errorMessage = null;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _stage = _Stage.error;
        _errorMessage = 'Could not read the selected file. Please try again.';
      });
    }
  }

  Future<void> _startScan() async {
    final file = _selectedFile;
    if (file == null || file.path == null) return;

    // Clearing any previous result BEFORE the new request starts is what
    // guarantees a stale finding from a prior APK can never remain
    // visible while a new one is being scanned (Phase 8's invariant).
    setState(() {
      _stage = _Stage.uploading;
      _result = null;
      _errorMessage = null;
    });

    // Captured before the disk-read await below so this doesn't use
    // BuildContext across an async gap - AppsRepository itself is a
    // stable, widget-tree-independent object once read.
    final appsRepository = context.read<AppsRepository>();
    try {
      // Read directly from disk (not via file_picker's withData/platform
      // channel - see _pickFile()'s comment) so a large APK's bytes never
      // have to cross the platform channel as one giant message.
      final bytes = await File(file.path!).readAsBytes();
      final result = await appsRepository.uploadApk(bytes, file.name);
      if (!mounted) return;
      setState(() {
        _result = result;
        _stage = _Stage.result;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = e.message;
        _stage = _Stage.error;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'The scan could not be completed. Please try again.';
        _stage = _Stage.error;
      });
    }
  }

  void _scanAnother() {
    setState(() {
      _stage = _Stage.pick;
      _selectedFile = null;
      _result = null;
      _errorMessage = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Upload APK')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: _buildBody(),
      ),
    );
  }

  Widget _buildBody() {
    switch (_stage) {
      case _Stage.uploading:
        return const LoadingView(message: 'Scanning APK for CWE-89 / CWE-295 vulnerabilities...');
      case _Stage.error:
        return ErrorStateView(
          message: _errorMessage ?? 'Something went wrong.',
          onRetry: _selectedFile != null ? _startScan : _pickFile,
        );
      case _Stage.result:
        return _ResultView(result: _result!, onScanAnother: _scanAnother);
      case _Stage.pick:
        return _PickView(selectedFile: _selectedFile, onPickFile: _pickFile, onScan: _startScan);
    }
  }
}

class _PickView extends StatelessWidget {
  final PlatformFile? selectedFile;
  final VoidCallback onPickFile;
  final VoidCallback onScan;

  const _PickView({required this.selectedFile, required this.onPickFile, required this.onScan});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.android, size: 64, color: AppColors.textSecondary),
        const SizedBox(height: 16),
        const Text(
          'Select an APK file to check it for SQL Injection (CWE-89) and '
          'Certificate Validation (CWE-295) issues.',
          textAlign: TextAlign.center,
          style: TextStyle(color: AppColors.textSecondary, fontSize: 14),
        ),
        const SizedBox(height: 24),
        if (selectedFile != null) ...[
          Card(
            child: ListTile(
              leading: const Icon(Icons.insert_drive_file_outlined),
              title: Text(selectedFile!.name, overflow: TextOverflow.ellipsis),
              subtitle: Text(_formatSize(selectedFile!.size)),
            ),
          ),
          const SizedBox(height: 16),
        ],
        OutlinedButton.icon(
          onPressed: onPickFile,
          icon: const Icon(Icons.folder_open),
          label: Text(selectedFile == null ? 'Choose APK' : 'Choose a different APK'),
        ),
        if (selectedFile != null) ...[
          const SizedBox(height: 12),
          ElevatedButton.icon(
            onPressed: onScan,
            icon: const Icon(Icons.security),
            label: const Text('Scan this APK'),
          ),
        ],
      ],
    );
  }

  String _formatSize(int bytes) {
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(0)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
}

class _ResultView extends StatelessWidget {
  final ApkScanResult result;
  final VoidCallback onScanAnother;

  const _ResultView({required this.result, required this.onScanAnother});

  @override
  Widget build(BuildContext context) {
    final ca = result.codeAnalysis;
    final cwe89Findings = ca.findings.where((f) => f.cwe == 'CWE-89').toList();
    final cwe295Findings = ca.findings.where((f) => f.cwe == 'CWE-295').toList();

    return RefreshIndicator(
      onRefresh: () async {},
      child: ListView(
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(result.apkName, style: Theme.of(context).textTheme.titleMedium, overflow: TextOverflow.ellipsis),
                  if (result.packageName != null) Text(result.packageName!, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                  const SizedBox(height: 12),
                  RiskBadge(riskLevel: result.riskLevel),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          _SummaryRow(
            filesScanned: ca.filesScanned,
            totalFindings: ca.totalFindings,
            cwe89Count: ca.cwe89Count,
            cwe295Count: ca.cwe295Count,
          ),
          if (ca.truncated)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(
                'This APK has more code than could be fully analyzed in this scan '
                '(${_truncationLabel(ca.truncationReason)}) - results above cover '
                'only the files that were actually scanned.',
                style: const TextStyle(color: AppColors.textSecondary, fontSize: 12, fontStyle: FontStyle.italic),
              ),
            ),
          const SizedBox(height: 16),
          if (ca.findings.isEmpty)
            const EmptyStateView(
              message: 'No CWE-89 or CWE-295 vulnerabilities detected.',
              icon: Icons.verified_outlined,
            )
          else ...[
            if (cwe89Findings.isNotEmpty) _FindingGroup(title: 'SQL Injection — CWE-89', findings: cwe89Findings),
            if (cwe295Findings.isNotEmpty) _FindingGroup(title: 'Certificate Validation — CWE-295', findings: cwe295Findings),
          ],
          if (ca.note != null) ...[
            const SizedBox(height: 8),
            Text(ca.note!, style: const TextStyle(color: AppColors.textSecondary, fontSize: 11, fontStyle: FontStyle.italic)),
          ],
          const SizedBox(height: 24),
          if (result.applicationId != null)
            OutlinedButton.icon(
              icon: const Icon(Icons.article_outlined),
              label: const Text('View full assessment'),
              onPressed: () => AppRouter.toApplicationDetailsById(context, result.applicationId!),
            ),
          const SizedBox(height: 10),
          ElevatedButton.icon(
            icon: const Icon(Icons.refresh),
            label: const Text('Scan another APK'),
            onPressed: onScanAnother,
          ),
        ],
      ),
    );
  }

  String _truncationLabel(String? reason) {
    switch (reason) {
      case 'max_classes_exceeded':
        return 'too many classes to analyze in one scan';
      case 'time_budget_exceeded':
        return 'the scan\'s time budget was reached';
      default:
        return 'scan limits were reached';
    }
  }
}

class _SummaryRow extends StatelessWidget {
  final int filesScanned;
  final int totalFindings;
  final int cwe89Count;
  final int cwe295Count;

  const _SummaryRow({
    required this.filesScanned,
    required this.totalFindings,
    required this.cwe89Count,
    required this.cwe295Count,
  });

  @override
  Widget build(BuildContext context) {
    // Display-side check of the same invariant the backend already
    // guarantees - this never overrides the server's numbers, it only
    // asserts (in debug builds) that they agree.
    assert(totalFindings == cwe89Count + cwe295Count);

    Widget stat(String label, String value) => Expanded(
          child: Column(
            children: [
              Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
              Text(label, style: const TextStyle(fontSize: 11, color: AppColors.textSecondary), textAlign: TextAlign.center),
            ],
          ),
        );

    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
        child: Row(
          children: [
            stat('Files scanned', '$filesScanned'),
            stat('Total findings', '$totalFindings'),
            stat('CWE-89', '$cwe89Count'),
            stat('CWE-295', '$cwe295Count'),
          ],
        ),
      ),
    );
  }
}

class _FindingGroup extends StatelessWidget {
  final String title;
  final List<ApkCodeFinding> findings;

  const _FindingGroup({required this.title, required this.findings});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          ...findings.map((f) => Card(
                margin: const EdgeInsets.only(bottom: 8),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              f.file ?? 'Unknown file',
                              style: const TextStyle(fontFamily: 'monospace', fontSize: 12, fontWeight: FontWeight.w600),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          if (f.severity != null)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: AppColors.forRiskLevel(f.severity).withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(f.severity!, style: TextStyle(color: AppColors.forRiskLevel(f.severity), fontSize: 11, fontWeight: FontWeight.bold)),
                            ),
                        ],
                      ),
                      if (f.line != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text('Line ${f.line}', style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                        ),
                      if (f.confidence != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text('Confidence: ${f.confidence}%', style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                        ),
                      if (f.explanation.isNotEmpty) ...[
                        const SizedBox(height: 6),
                        ...f.explanation.map((s) => Text('• $s', style: const TextStyle(fontSize: 12))),
                      ],
                    ],
                  ),
                ),
              )),
        ],
      ),
    );
  }
}
