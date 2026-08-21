import 'package:flutter/material.dart';
import '../models/session_info.dart';
import '../theme/app_theme.dart';

class SessionPill extends StatelessWidget {
  final SessionInfo info;
  const SessionPill({super.key, required this.info});

  Color get _color {
    switch (info.status) {
      case SessionStatus.live:
        return AppColors.bull;
      case SessionStatus.deadZone:
      case SessionStatus.lastCall:
        return const Color(0xFFF5A623);
      case SessionStatus.preOpen:
        return AppColors.trinity;
      case SessionStatus.closed:
      case SessionStatus.weekend:
        return AppColors.mist;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _color;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.14),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(width: 7, height: 7, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
          const SizedBox(width: 6),
          Text(
            info.label,
            style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: 0.5),
          ),
        ],
      ),
    );
  }
}
