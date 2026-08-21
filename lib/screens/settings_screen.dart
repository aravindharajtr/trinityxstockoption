import 'package:flutter/material.dart';
import '../models/strategy_config.dart';
import '../theme/app_theme.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final rows = <MapEntry<String, String>>[
      MapEntry('Initial capital', '₹${StrategyConfig.initialCapital}'),
      MapEntry('Max risk / trade', '${StrategyConfig.maxRiskPerTradePct.toStringAsFixed(0)}%'),
      MapEntry('Max daily loss', '${StrategyConfig.maxDailyLossPct.toStringAsFixed(0)}%'),
      MapEntry('Max trades / day', '${StrategyConfig.maxTradesPerDay}'),
      MapEntry('Max open positions', '${StrategyConfig.maxOpenPositions}'),
      MapEntry('Stop loss', '${StrategyConfig.stopLossPct.toStringAsFixed(0)}%'),
      MapEntry('Target', '${StrategyConfig.targetPct.toStringAsFixed(0)}%'),
      MapEntry('Trailing activates at', '${StrategyConfig.trailingActivatePct.toStringAsFixed(0)}%'),
      MapEntry('Trailing stop', '${StrategyConfig.trailingStopPct.toStringAsFixed(0)}%'),
      MapEntry('Scan start', StrategyConfig.scanStart),
      MapEntry('No new trades after', StrategyConfig.noNewTradesAfter),
      MapEntry('Dead zone', '${StrategyConfig.deadZoneStart}–${StrategyConfig.deadZoneEnd}'),
      MapEntry('Auto exit', StrategyConfig.autoExitTime),
    ];

    return Scaffold(
      appBar: AppBar(title: const Text('Strategy')),
      body: ListView.separated(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: rows.length,
        separatorBuilder: (_, __) => const Divider(height: 1, color: AppColors.slateHigh),
        itemBuilder: (context, i) {
          final row = rows[i];
          return ListTile(
            title: Text(row.key, style: const TextStyle(color: AppColors.foam)),
            trailing: Text(row.value, style: numeralStyle(size: 15)),
          );
        },
      ),
    );
  }
}
