import 'strategy_config.dart';

enum SessionStatus { preOpen, live, deadZone, lastCall, closed, weekend }

class SessionInfo {
  final SessionStatus status;
  final String label;
  const SessionInfo(this.status, this.label);
}

int _toMinutes(String hhmm) {
  final p = hhmm.split(':');
  return int.parse(p[0]) * 60 + int.parse(p[1]);
}

// Assumes the device clock is already IST.
SessionInfo currentSessionInfo(DateTime now) {
  if (now.weekday == DateTime.saturday || now.weekday == DateTime.sunday) {
    return const SessionInfo(SessionStatus.weekend, 'CLOSED · WEEKEND');
  }

  final nowMin = now.hour * 60 + now.minute;
  final scanStart = _toMinutes(StrategyConfig.scanStart);
  final deadStart = _toMinutes(StrategyConfig.deadZoneStart);
  final deadEnd = _toMinutes(StrategyConfig.deadZoneEnd);
  final noNew = _toMinutes(StrategyConfig.noNewTradesAfter);
  final autoExit = _toMinutes(StrategyConfig.autoExitTime);

  if (nowMin < scanStart) return const SessionInfo(SessionStatus.preOpen, 'PRE-OPEN');
  if (nowMin >= autoExit) return const SessionInfo(SessionStatus.closed, 'CLOSED');
  if (nowMin >= deadStart && nowMin < deadEnd) {
    return const SessionInfo(SessionStatus.deadZone, 'DEAD ZONE');
  }
  if (nowMin >= noNew) return const SessionInfo(SessionStatus.lastCall, 'NO NEW TRADES');
  return const SessionInfo(SessionStatus.live, 'LIVE · SCANNING');
}
