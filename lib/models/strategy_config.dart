// Hand-mirrored from config.py — update both when either changes.
class StrategyConfig {
  StrategyConfig._();

  static const int initialCapital = 500000;
  static const double maxRiskPerTradePct = 10;
  static const double maxDailyLossPct = 2;
  static const int maxTradesPerDay = 10;
  static const int maxOpenPositions = 5;

  static const double stopLossPct = 15;
  static const double targetPct = 30;
  static const double trailingActivatePct = 12;
  static const double trailingStopPct = 8;

  static const String scanStart = '09:25';
  static const String noNewTradesAfter = '14:15';
  static const String autoExitTime = '15:00';
  static const String deadZoneStart = '13:00';
  static const String deadZoneEnd = '13:30';
}
