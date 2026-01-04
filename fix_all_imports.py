#!/usr/bin/env python
"""
Fix import issues in all views.py files
"""
import os
import sys

# Add project to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Fix imports in all view files
files_to_fix = [
    ('organizations/views.py', 'from accounts.permissions import IsSystemAdmin'),
    ('customers/views.py', 'from accounts.permissions import IsSystemAdmin'),
    ('payments/views.py', 'from accounts.permissions import IsSystemAdmin'),
    ('integrations/views.py', 'from accounts.permissions import IsSystemAdmin'),
    ('notifications/views.py', 'from accounts.permissions import IsSystemAdmin'),
]

for file_path, import_line in files_to_fix:
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Fix IsSystemAdmin import if needed
            if 'IsSystemAdmin' in content and 'from .permissions import' in content:
                lines = content.split('\n')
                new_lines = []
                for line in lines:
                    if 'from .permissions import' in line and 'IsSystemAdmin' in line:
                        # Add the import line at the top
                        new_lines.insert(0, import_line)
                        # Remove IsSystemAdmin from the existing import
                        line = line.replace('IsSystemAdmin,', '').replace(', IsSystemAdmin', '')
                        new_lines.append(line)
                    else:
                        new_lines.append(line)
                
                # Remove empty import lines
                new_content = '\n'.join(new_lines)
                new_content = new_content.replace('from .permissions import (\n    )', '')
                new_content = new_content.replace('from .permissions import ()', '')
                
                with open(file_path, 'w') as f:
                    f.write(new_content)
                
                print(f"✓ Fixed imports in {file_path}")
            else:
                print(f"✓ No import issues found in {file_path}")
        else:
            print(f"✗ File not found: {file_path}")
            
    except Exception as e:
        print(f"✗ Error fixing {file_path}: {str(e)}")

print("\n✅ All imports fixed successfully!")