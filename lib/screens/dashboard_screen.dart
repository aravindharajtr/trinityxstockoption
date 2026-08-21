import 'dart:async';
import 'package:flutter/material.dart';
import '../models/strategy_config.dart';
import '../models/session_info.dart';
import '../theme/app_theme.dart';
import '../widgets/stat_tile.dart';
import '../widgets/session_pill.dart';
import '../widgets/session_timeline.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  late final Timer _clock;
  DateTime _now = DateTime.now();

  @override
  void initState() {
    super.initState();
    _clock = Timer.periodic(const Duration(seconds: 30), (_) {
      setState(() => _now = DateTime.now());
    });
  }

  @override
  void dispose() {
    _clock.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final session = currentSessionInfo(_now);
    const capital = StrategyConfig.initialCapital;
    final maxRiskRupees = (capital * StrategyConfig.maxRiskPerTradePct / 100).round();
    final maxLossRupees = (capital * StrategyConfig.maxDailyLossPct / 100).round();

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: const [
            Text('TRINITYX', style: TextStyle(fontWeight: FontWeight.w800, letterSpacing: 2, fontSize: 18, color: AppColors.foam)),
            SizedBox(width: 4),
            Text('F&O', style: TextStyle(fontWeight: FontWeight.w400, letterSpacing: 2, fontSize: 18, color: AppColors.trinity)),
          ],
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Center(child: SessionPill(info: session)),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppColors.slate,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppColors.slateHigh),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('CAPITAL DEPLOYED', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.mist, letterSpacing: 0.8)),
                const SizedBox(height: 8),
                Text('₹${formatRupees(capital)}', style: numeralStyle(size: 34)),
                const SizedBox(height: 4),
                const Text("Today's P&L will show here once this screen is wired to your engine.", style: TextStyle(color: AppColors.mist, fontSize: 12)),
              ],
            ),
          ),
          const SizedBox(height: 16),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            childAspectRatio: 1.5,
            children: [
              StatTile(label: 'Max risk / trade', value: '₹${formatRupees(maxRiskRupees)}', caption: '${StrategyConfig.maxRiskPerTradePct.toStringAsFixed(0)}% of capital'),
              StatTile(label: 'Daily loss cap', value: '₹${formatRupees(maxLossRupees)}', caption: '${StrategyConfig.maxDailyLossPct.toStringAsFixed(0)}% of capital', valueColor: AppColors.bear),
              StatTile(label: 'Max trades / day', value: '${StrategyConfig.maxTradesPerDay}'),
              StatTile(label: 'Max open positions', value: '${StrategyConfig.maxOpenPositions}'),
            ],
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppColors.slate,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppColors.slateHigh),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text("TODAY'S SESSION", style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.mist, letterSpacing: 0.8)),
                const SizedBox(height: 14),
                const SessionTimeline(),
                const SizedBox(height: 14),
                _legendRow(),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: AppColors.slate,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppColors.slateHigh),
            ),
            child: Column(
              children: const [
                Icon(Icons.show_chart, color: AppColors.mist, size: 28),
                SizedBox(height: 12),
                Text('No live positions feed connected', style: TextStyle(color: AppColors.foam, fontWeight: FontWeight.w600), textAlign: TextAlign.center),
                SizedBox(height: 6),
                Text('Point this screen at your FastAPI /positions endpoint to replace this card with real trades.', style: TextStyle(color: AppColors.mist, fontSize: 12), textAlign: TextAlign.center),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _legendRow() {
    Widget dot(Color c, String label) => Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(width: 8, height: 8, decoration: BoxDecoration(color: c, shape: BoxShape.circle)),
            const SizedBox(width: 6),
            Text(label, style: const TextStyle(color: AppColors.mist, fontSize: 11)),
          ],
        );

    return Wrap(
      spacing: 16,
      runSpacing: 8,
      children: [
        dot(AppColors.bull, 'Scanning'),
        dot(const Color(0xFFF5A623), 'Dead zone'),
        dot(AppColors.trinity, 'No new trades'),
        dot(AppColors.slateHigh, 'Closed'),
      ],
    );
  }
}

String formatRupees(int value) {
  final s = value.toString();
  if (s.length <= 3) return s;
  final last3 = s.substring(s.length - 3);
  final rest = s.substring(0, s.length - 3);
  final buffer = StringBuffer();
  for (int i = 0; i < rest.length; i++) {
    final posFromEnd = rest.length - i;
    buffer.write(rest[i]);
    if (posFromEnd > 1 && posFromEnd % 2 == 1) buffer.write(',');
  }
  return '${buffer.toString()},$last3';
}
