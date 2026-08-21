import 'package:flutter/material.dart';
import '../models/strategy_config.dart';
import '../theme/app_theme.dart';

class SessionTimeline extends StatelessWidget {
  const SessionTimeline({super.key});

  @override
  Widget build(BuildContext context) {
    const dayStart = 9 * 60 + 15;
    const dayEnd = 15 * 60 + 30;

    int toMin(String hhmm) {
      final p = hhmm.split(':');
      return int.parse(p[0]) * 60 + int.parse(p[1]);
    }

    final segments = <_Seg>[
      _Seg(dayStart, toMin(StrategyConfig.scanStart), AppColors.slateHigh),
      _Seg(toMin(StrategyConfig.scanStart), toMin(StrategyConfig.deadZoneStart), AppColors.bull),
      _Seg(toMin(StrategyConfig.deadZoneStart), toMin(StrategyConfig.deadZoneEnd), const Color(0xFFF5A623)),
      _Seg(toMin(StrategyConfig.deadZoneEnd), toMin(StrategyConfig.noNewTradesAfter), AppColors.bull),
      _Seg(toMin(StrategyConfig.noNewTradesAfter), toMin(StrategyConfig.autoExitTime), AppColors.trinity),
      _Seg(toMin(StrategyConfig.autoExitTime), dayEnd, AppColors.slateHigh),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: SizedBox(
            height: 10,
            child: Row(
              children: segments
                  .map((s) => Expanded(
                        flex: (s.end - s.start).clamp(1, 999999),
                        child: Container(color: s.color),
                      ))
                  .toList(),
            ),
          ),
        ),
        const SizedBox(height: 8),
        const Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('09:15', style: TextStyle(color: AppColors.mist, fontSize: 11)),
            Text('15:30', style: TextStyle(color: AppColors.mist, fontSize: 11)),
          ],
        ),
      ],
    );
  }
}

class _Seg {
  final int start;
  final int end;
  final Color color;
  const _Seg(this.start, this.end, this.color);
}
