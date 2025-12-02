#!/usr/bin/env python
"""
Script to generate Prisma Client Python using the Python prisma package.
This uses the Python package which downloads Prisma binaries automatically.
No Node.js or npm installation required.
"""
import subprocess
import sys
import os
from pathlib import Path

# Get the backend directory
backend_dir = Path(__file__).parent
os.chdir(backend_dir)

schema_path = backend_dir / "prisma" / "schema.prisma"

print(f"Generating Prisma Client from {schema_path}...")
print("Using Python prisma package (binaries will be downloaded automatically)...\n")

# Step 1: Fetch Prisma binaries (downloads from online, stores locally)
print("Step 1: Fetching Prisma binaries...")
try:
    result = subprocess.run(
        [sys.executable, "-m", "prisma", "py", "fetch"],
        cwd=backend_dir,
        capture_output=True,
        text=True,
        check=False
    )
    if result.returncode == 0:
        print("✓ Binaries fetched successfully")
    else:
        print(f"⚠ Warning: Binary fetch had issues: {result.stderr}")
        print("Continuing anyway...")
except (OSError, subprocess.SubprocessError) as e:
    print(f"⚠ Warning: Could not fetch binaries: {e}")
    print("Continuing anyway...")

# Step 2: Generate Prisma Client using Python package
print("\nStep 2: Generating Prisma Client...")
try:
    # Set environment variable for schema path
    os.environ["PRISMA_SCHEMA_PATH"] = str(schema_path)   
    result = subprocess.run(
        [sys.executable, "-m", "prisma", "py", "generate"],
        cwd=backend_dir,
        capture_output=True,
        text=True,
        check=False
    )
    if result.returncode == 0:
        print("✓ Prisma Client generated successfully!")
        if result.stdout:
            print(result.stdout)
        sys.exit(0)
    else:
        print("✗ Error generating Prisma Client:")
        print(result.stderr)
        sys.exit(1)
except (OSError, subprocess.SubprocessError) as e:
    print(f"✗ Error: {e}")
    sys.exit(1)