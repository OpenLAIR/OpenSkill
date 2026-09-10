#!/usr/bin/env python3
"""Generate all Java source files for the LongestSessionPerJob Flink job.

Usage: python3 generate_java.py [workspace_dir]
Default workspace_dir: /app/workspace

This generates:
1. TaskEvent.java - data type for task events (Google Cluster Data v2)
2. JobEvent.java - data type for job events
3. LongestSessionPerJob.java - main Flink job
"""
import os
import sys
import shutil

def get_workspace_dir():
    return sys.argv[1] if len(sys.argv) > 1 else '/app/workspace'

def write_file(base_dir, rel_path, content):
    path = os.path.join(base_dir, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
    print(f"Written: {path}")

def generate_all(base_dir):
    # Copy template files from skill's templates directory
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(skill_dir, 'templates')
    
    files = [
        ('TaskEvent.java', 'src/main/java/clusterdata/datatypes/TaskEvent.java'),
        ('JobEvent.java', 'src/main/java/clusterdata/datatypes/JobEvent.java'),
        ('LongestSessionPerJob.java', 'src/main/java/clusterdata/query/LongestSessionPerJob.java'),
    ]
    
    for template_name, dest_path in files:
        src = os.path.join(templates_dir, template_name)
        dest = os.path.join(base_dir, dest_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(src, dest)
        print(f"Copied: {src} -> {dest}")

if __name__ == '__main__':
    base = get_workspace_dir()
    generate_all(base)
    print("All Java files generated successfully.")
