import subprocess
import os
import re
import logging
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MVN_NS = "http://maven.apache.org/POM/4.0.0"
NS_MAP = {'m': MVN_NS}


def execute_maven_build(project_dir, goals, java_home=None, timeout_secs=600, pom_file=None):
    """Execute a Maven build and capture output."""
    mvn_executable = './mvnw' if os.path.exists(os.path.join(project_dir, 'mvnw')) else 'mvn'
    command = [mvn_executable, '-B', '-e']
    if pom_file:
        command.extend(['-f', pom_file])
    command.extend(goals)
    
    env = os.environ.copy()
    if java_home:
        env['JAVA_HOME'] = java_home
        env['PATH'] = f"{os.path.join(java_home, 'bin')}{os.pathsep}{env.get('PATH', '')}"
    
    try:
        result = subprocess.run(
            command, cwd=project_dir, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=timeout_secs, check=False
        )
        return result
    except subprocess.TimeoutExpired as e:
        logger.error(f"Build timed out after {timeout_secs}s")
        raise
    except FileNotFoundError:
        logger.error("Maven executable not found")
        raise


def parse_compilation_errors(maven_log):
    """Extract Java compilation errors from Maven log."""
    pattern = re.compile(
        r'\[ERROR\]\s+(?P<file>.+?\.java):\[(?P<line>\d+),(?P<col>\d+)\]\s+(?P<msg>.+)'
    )
    errors = []
    for match in pattern.finditer(maven_log):
        errors.append({
            'file': match.group('file').strip(),
            'line': int(match.group('line')),
            'col': int(match.group('col')),
            'message': match.group('msg').strip()
        })
    return errors


def parse_dependency_errors(maven_log):
    """Extract dependency resolution failures."""
    pattern = re.compile(
        r'Failure to find (?P<artifact>[A-Za-z0-9_.:-]+:[A-Za-z0-9_.:-]+:(?:jar|war|pom):[A-Za-z0-9_.:-]+)'
    )
    return [m.group('artifact') for m in pattern.finditer(maven_log)]


def parse_plugin_errors(maven_log):
    """Extract plugin execution failures."""
    pattern = re.compile(
        r'\[ERROR\] Failed to execute goal ([^:]+:[^:]+:[^:]+:[^\s]+)\s+\(([^)]+)\)\s+on project ([^:]+):(.+?)(?=\[ERROR\]|$)',
        re.DOTALL
    )
    errors = []
    for m in pattern.finditer(maven_log):
        errors.append({
            'plugin': m.group(1).strip(),
            'execution': m.group(2).strip(),
            'project': m.group(3).strip(),
            'message': m.group(4).strip()
        })
    return errors


def parse_pom_errors(maven_log):
    """Extract POM-related errors like missing POM files."""
    errors = []
    # Non-readable POM
    pattern = re.compile(r'Non-readable POM ([^:]+):\s*(.+?)(?:\s*\(([^)]+)\))?$', re.MULTILINE)
    for m in pattern.finditer(maven_log):
        errors.append({
            'type': 'non_readable_pom',
            'pom_path': m.group(1).strip(),
            'reason': m.group(3).strip() if m.group(3) else m.group(2).strip()
        })
    # Build could not read project
    pattern2 = re.compile(r'The build could not read (\d+) project')
    for m in pattern2.finditer(maven_log):
        errors.append({
            'type': 'unreadable_projects',
            'count': int(m.group(1))
        })
    return errors


def parse_version_incompatibilities(maven_log):
    """Extract Java source/target version incompatibility errors."""
    pattern = re.compile(
        r'Source option (\S+) is no longer supported\.\s*Use (\S+) or later'
    )
    errors = []
    for m in pattern.finditer(maven_log):
        errors.append({
            'type': 'source_version',
            'unsupported': m.group(1),
            'minimum': m.group(2)
        })
    pattern2 = re.compile(
        r'Target option (\S+) is no longer supported\.\s*Use (\S+) or later'
    )
    for m in pattern2.finditer(maven_log):
        errors.append({
            'type': 'target_version',
            'unsupported': m.group(1),
            'minimum': m.group(2)
        })
    return errors


def detect_java_version_from_pom(pom_path):
    """Parse pom.xml to find Java source/target version."""
    try:
        ET.register_namespace('', MVN_NS)
        tree = ET.parse(pom_path)
        root = tree.getroot()
        
        target = root.find('.//m:properties/m:maven.compiler.target', NS_MAP)
        if target is not None and target.text:
            return target.text.strip()
        
        java_ver = root.find('.//m:properties/m:java.version', NS_MAP)
        if java_ver is not None and java_ver.text:
            return java_ver.text.strip()
        
        plugins = root.findall('.//m:plugin', NS_MAP)
        for plugin in plugins:
            aid = plugin.find('m:artifactId', NS_MAP)
            if aid is not None and aid.text == 'maven-compiler-plugin':
                cfg_target = plugin.find('.//m:configuration/m:target', NS_MAP)
                if cfg_target is not None and cfg_target.text:
                    return cfg_target.text.strip()
    except ET.ParseError as e:
        logger.error(f"Invalid XML in {pom_path}: {e}")
    return None


def classify_build_failure(maven_log):
    """Classify the type of build failure from Maven log output."""
    results = {
        'pom_errors': parse_pom_errors(maven_log),
        'compilation_errors': parse_compilation_errors(maven_log),
        'dependency_errors': parse_dependency_errors(maven_log),
        'plugin_errors': parse_plugin_errors(maven_log),
        'version_errors': parse_version_incompatibilities(maven_log),
    }
    
    # Determine primary failure type
    if results['pom_errors']:
        results['primary_type'] = 'pom_configuration'
    elif results['version_errors']:
        results['primary_type'] = 'version_incompatibility'
    elif results['dependency_errors']:
        results['primary_type'] = 'dependency_resolution'
    elif results['compilation_errors']:
        results['primary_type'] = 'compilation'
    elif results['plugin_errors']:
        results['primary_type'] = 'plugin_execution'
    else:
        results['primary_type'] = 'unknown'
    
    return results


def analyze_travis_yml(travis_yml_path):
    """Parse .travis.yml to extract build commands and identify issues."""
    issues = []
    if not os.path.exists(travis_yml_path):
        return {'exists': False, 'issues': [{'type': 'missing_file', 'message': '.travis.yml not found'}]}
    
    with open(travis_yml_path, 'r') as f:
        content = f.read()
    
    # Check for file references in mvn commands
    mvn_pattern = re.compile(r'mvn\s+.*-f\s+(\S+)')
    for m in mvn_pattern.finditer(content):
        referenced_file = m.group(1)
        project_dir = os.path.dirname(travis_yml_path)
        full_path = os.path.join(project_dir, referenced_file)
        if not os.path.exists(full_path):
            issues.append({
                'type': 'missing_pom_reference',
                'referenced_file': referenced_file,
                'full_path': full_path,
                'line': content[:m.start()].count('\n') + 1
            })
    
    return {'exists': True, 'content': content, 'issues': issues}


def write_diagnosis_report(report_path, analysis_results, log_analysis=None, travis_analysis=None):
    """Write the diagnosis report to failed_reasons.txt."""
    with open(report_path, 'w') as f:
        f.write("# Build Failure Diagnosis Report\n\n")
        
        if travis_analysis and travis_analysis.get('issues'):
            f.write("## .travis.yml Issues\n")
            for issue in travis_analysis['issues']:
                f.write(f"- {issue['type']}: {issue.get('message', '')}\n")
                if issue['type'] == 'missing_pom_reference':
                    f.write(f"  Referenced file: {issue['referenced_file']}\n")
                    f.write(f"  File not found at: {issue['full_path']}\n")
            f.write("\n")
        
        if log_analysis:
            f.write(f"## Primary Failure Type: {log_analysis.get('primary_type', 'unknown')}\n\n")
            
            if log_analysis.get('pom_errors'):
                f.write("### POM Errors\n")
                for err in log_analysis['pom_errors']:
                    f.write(f"- {err['type']}: {err.get('pom_path', '')} - {err.get('reason', '')}\n")
                f.write("\n")
            
            if log_analysis.get('compilation_errors'):
                f.write("### Compilation Errors\n")
                for err in log_analysis['compilation_errors']:
                    f.write(f"- {err['file']}:[{err['line']},{err['col']}] {err['message']}\n")
                f.write("\n")
            
            if log_analysis.get('dependency_errors'):
                f.write("### Dependency Errors\n")
                for err in log_analysis['dependency_errors']:
                    f.write(f"- Missing: {err}\n")
                f.write("\n")
            
            if log_analysis.get('version_errors'):
                f.write("### Version Incompatibilities\n")
                for err in log_analysis['version_errors']:
                    f.write(f"- {err['type']}: {err['unsupported']} -> use {err['minimum']}+\n")
                f.write("\n")
        
        f.write("## Proposed Fixes\n")
        if travis_analysis and travis_analysis.get('issues'):
            for issue in travis_analysis['issues']:
                if issue['type'] == 'missing_pom_reference':
                    f.write(f"- Fix .travis.yml: change '{issue['referenced_file']}' to correct filename\n")
        
        if log_analysis:
            if log_analysis.get('version_errors'):
                f.write("- Update pom.xml source/target version to supported version\n")
            if log_analysis.get('compilation_errors'):
                f.write("- Fix compilation errors in source files\n")
    
    logger.info(f"Diagnosis report written to {report_path}")
