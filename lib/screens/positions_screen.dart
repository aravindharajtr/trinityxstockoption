import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class PositionsScreen extends StatelessWidget {
  const PositionsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Positions')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: const [
              Icon(Icons.show_chart, color: AppColors.mist, size: 36),
              SizedBox(height: 16),
              Text('No positions feed yet', style: TextStyle(color: AppColors.foam, fontWeight: FontWeight.w600, fontSize: 16)),
              SizedBox(height: 8),
              Text(
                'Built to render open positions from your trading engine. '
                'Wire it to a GET /positions endpoint on your FastAPI layer '
                'to replace this placeholder.',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppColors.mist, fontSize: 13, height: 1.5),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
