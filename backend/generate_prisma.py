#!/usr/bin/env python
"""
Script to generate Prisma Client Python
This is a workaround for the Prisma CLI generator issue
"""
import subprocess
import sys
import os
from pathlib import Path

# Get the backend directory
backend_dir = Path(__file__).parent
os.chdir(backend_dir)

# Try using npx prisma generate with explicit schema path
schema_path = backend_dir / "prisma" / "schema.prisma"

print(f"Generating Prisma Client from {schema_path}...")

# First, try to fetch binaries
try:
    result = subprocess.run(
        [sys.executable, "-m", "prisma", "py", "fetch"],
        cwd=backend_dir,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("✓ Binaries fetched successfully")
    else:
        print(f"⚠ Warning: Binary fetch had issues: {result.stderr}")
except Exception as e:
    print(f"⚠ Warning: Could not fetch binaries: {e}")

# Try using npx prisma generate
try:
    result = subprocess.run(
        ["npx", "prisma", "generate", "--schema", str(schema_path)],
        cwd=backend_dir,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("✓ Prisma Client generated successfully!")
        print(result.stdout)
        sys.exit(0)
    else:
        print(f"✗ Error: {result.stderr}")
        # Try alternative method
        print("\nTrying alternative method...")
except Exception as e:
    print(f"✗ Error with npx: {e}")
    print("\nTrying alternative method...")

# Alternative: Use Python prisma package directly
try:
    # Set environment variable for schema path
    os.environ["PRISMA_SCHEMA_PATH"] = str(schema_path)
    
    result = subprocess.run(
        [sys.executable, "-m", "prisma", "py", "generate"],
        cwd=backend_dir,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("✓ Prisma Client generated successfully!")
        print(result.stdout)
        sys.exit(0)
    else:
        print(f"✗ Error: {result.stderr}")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)

