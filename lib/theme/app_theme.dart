import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  static const ink = Color(0xFF0A0E12);
  static const slate = Color(0xFF151B22);
  static const slateHigh = Color(0xFF212A35);
  static const foam = Color(0xFFEAF0F6);
  static const mist = Color(0xFF7E8C9A);
  static const bull = Color(0xFF2FD180);
  static const bear = Color(0xFFFF5D5D);
  static const trinity = Color(0xFF7C6CF6);
}

ThemeData buildAppTheme() {
  final base = ThemeData(
    brightness: Brightness.dark,
    useMaterial3: true,
    scaffoldBackgroundColor: AppColors.ink,
    colorScheme: const ColorScheme.dark(
      surface: AppColors.slate,
      primary: AppColors.trinity,
      secondary: AppColors.trinity,
      error: AppColors.bear,
    ),
  );

  return base.copyWith(
    textTheme: base.textTheme.apply(
      bodyColor: AppColors.foam,
      displayColor: AppColors.foam,
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.ink,
      elevation: 0,
      centerTitle: false,
      foregroundColor: AppColors.foam,
    ),
  );
}

// Tabular figures keep P&L columns aligned like a real ticker.
TextStyle numeralStyle({
  required double size,
  FontWeight weight = FontWeight.w600,
  Color color = AppColors.foam,
}) {
  return TextStyle(
    fontSize: size,
    fontWeight: weight,
    color: color,
    fontFeatures: const [FontFeature.tabularFigures()],
    letterSpacing: -0.2,
  );
}
