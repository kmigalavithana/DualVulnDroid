import 'package:flutter/material.dart';

/// Resolves the plain string icon keys stored on [AppCategory]/[AppInfo]
/// (kept string-based there so those model files have no Flutter
/// dependency) to real Material [IconData]. Unknown keys fall back to a
/// generic app icon rather than throwing.
IconData resolveIconKey(String key) {
  switch (key) {
    case 'work_outline':
      return Icons.work_outline;
    case 'note_alt_outlined':
      return Icons.note_alt_outlined;
    case 'photo_outlined':
      return Icons.photo_outlined;
    case 'movie_creation_outlined':
      return Icons.movie_creation_outlined;
    case 'picture_as_pdf_outlined':
      return Icons.picture_as_pdf_outlined;
    case 'music_note_outlined':
      return Icons.music_note_outlined;
    case 'school_outlined':
      return Icons.school_outlined;
    case 'chat_bubble_outline':
      return Icons.chat_bubble_outline;
    case 'folder_outlined':
      return Icons.folder_outlined;
    case 'public_outlined':
      return Icons.public_outlined;
    case 'build_outlined':
      return Icons.build_outlined;
    case 'apps_outlined':
      return Icons.apps_outlined;
    case 'description_outlined':
      return Icons.description_outlined;
    case 'sticky_note_2_outlined':
      return Icons.sticky_note_2_outlined;
    case 'auto_fix_high_outlined':
      return Icons.auto_fix_high_outlined;
    case 'movie_filter_outlined':
      return Icons.movie_filter_outlined;
    case 'graphic_eq_outlined':
      return Icons.graphic_eq_outlined;
    case 'translate_outlined':
      return Icons.translate_outlined;
    case 'forum_outlined':
      return Icons.forum_outlined;
    case 'cloud_outlined':
      return Icons.cloud_outlined;
    case 'travel_explore_outlined':
      return Icons.travel_explore_outlined;
    case 'calculate_outlined':
      return Icons.calculate_outlined;
    case 'speed_outlined':
      return Icons.speed_outlined;
    case 'checklist_outlined':
      return Icons.checklist_outlined;
    case 'groups_outlined':
      return Icons.groups_outlined;
    default:
      return Icons.apps_outlined;
  }
}
