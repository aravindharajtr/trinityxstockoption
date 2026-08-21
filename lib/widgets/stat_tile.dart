import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class StatTile extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;
  final String? caption;

  const StatTile({
    super.key,
    required this.label,
    required this.value,
    this.valueColor,
    this.caption,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.slate,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.slateHigh),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label.toUpperCase(),
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: AppColors.mist,
              letterSpacing: 0.8,
            ),
          ),
          const SizedBox(height: 8),
          Text(value, style: numeralStyle(size: 22, color: valueColor ?? AppColors.foam)),
          if (caption != null) ...[
            const SizedBox(height: 4),
            Text(caption!, style: const TextStyle(fontSize: 12, color: AppColors.mist)),
          ],
        ],
      ),
    );
  }
}
