# System Configuration Settings
class SystemConfig:
    # Balance threshold settings
    BALANCE_THRESHOLD_PERCENTAGE = 80  # 80% of semester fees
    DEFAULT_SEMESTER_FEES = {
        'certificate': 500.00,
        'diploma': 750.00,
        'undergraduate': 1000.00,
        'postgraduate': 1500.00
    }
    
    # Transaction settings
    SEMESTER_TRANSACTION_TYPES = {
        'tuition': 'Tuition Fees',
        'registration': 'Registration Fees',
        'examination': 'Examination Fees',
        'library': 'Library Fees',
        'technology': 'Technology Fees',
        'other': 'Other Semester Fees'
    }
    
    # Staff privilege levels that can override balance checks
    GRADE_VIEW_PRIVILEGES = ['admin', 'registrar', 'finance', 'academics', 'admin_dvc', 'ict', 'admin_vc']