import re
import os

def find_sequential_awaits(filepath):
    """Find sequential await statements that could be parallelized with Promise.all."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Pattern: multiple consecutive 'const X = await funcCall();' lines
    pattern = r'((?:^\s*const\s+\w+\s*=\s*await\s+\w+\([^)]*\);?\s*\n){2,})'
    matches = re.findall(pattern, content, re.MULTILINE)
    
    issues = []
    for match in matches:
        lines = [l.strip() for l in match.strip().split('\n') if l.strip()]
        issues.append({
            'type': 'sequential_awaits',
            'lines': lines,
            'count': len(lines),
            'suggestion': 'Use Promise.all to parallelize independent awaits'
        })
    return issues

def fix_sequential_awaits(filepath):
    """Replace sequential awaits with Promise.all pattern."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find blocks of consecutive await statements
    # Match: const varName = await functionCall(args);
    await_pattern = r'^(\s*)const\s+(\w+)\s*=\s*await\s+(\w+\([^)]*\));?\s*$'
    
    lines = content.split('\n')
    result_lines = []
    i = 0
    
    while i < len(lines):
        # Check if current line is an await statement
        match = re.match(await_pattern, lines[i])
        if match:
            # Collect consecutive await statements
            await_group = []
            indent = match.group(1)
            while i < len(lines):
                m = re.match(await_pattern, lines[i])
                if m and m.group(1) == indent:
                    await_group.append({
                        'var': m.group(2),
                        'call': m.group(3),
                        'indent': m.group(1)
                    })
                    i += 1
                else:
                    break
            
            if len(await_group) >= 2:
                # Replace with Promise.all
                vars_str = ', '.join(a['var'] for a in await_group)
                calls = [f"{indent}  {a['call']}," for a in await_group]
                result_lines.append(f"{indent}const [{vars_str}] = await Promise.all([")
                result_lines.extend(calls)
                result_lines.append(f"{indent}]);")
            else:
                # Single await, keep as is
                for a in await_group:
                    result_lines.append(f"{a['indent']}const {a['var']} = await {a['call']};")
        else:
            result_lines.append(lines[i])
            i += 1
    
    new_content = '\n'.join(result_lines)
    with open(filepath, 'w') as f:
        f.write(new_content)
    return True

def find_artificial_delays(filepath):
    """Find artificial delays like setTimeout wrapped in Promise."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    pattern = r'await\s+new\s+Promise.*setTimeout'
    matches = re.findall(pattern, content)
    return [{'type': 'artificial_delay', 'match': m} for m in matches]

def remove_artificial_delays(filepath):
    """Remove artificial delay patterns from file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Remove lines with: await new Promise(resolve => setTimeout(resolve, N));
    pattern = r'\s*await\s+new\s+Promise\s*\(\s*(?:resolve|res)\s*=>\s*setTimeout\s*\(\s*(?:resolve|res)\s*,\s*\d+\s*\)\s*\)\s*;?\s*\n?'
    content = re.sub(pattern, '', content)
    
    with open(filepath, 'w') as f:
        f.write(content)
    return True

def apply_api_fixes(filepath):
    """Apply all API optimization fixes to a file."""
    remove_artificial_delays(filepath)
    fix_sequential_awaits(filepath)
    return True
