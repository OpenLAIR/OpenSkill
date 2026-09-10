import re
import os

def wrap_component_in_memo(filepath, component_name):
    """Wrap a React component export in React.memo."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add memo import
    if "import { memo }" not in content and "import React" not in content:
        # Check if there's already a react import to extend
        react_import = re.search(r"import\s*\{([^}]+)\}\s*from\s*['\"]react['\"];", content)
        if react_import:
            existing = react_import.group(1)
            if 'memo' not in existing:
                new_import = f"import {{{existing}, memo }} from 'react';"
                content = content[:react_import.start()] + new_import + content[react_import.end():]
        else:
            # Add new import at the top (after 'use client' if present)
            if "'use client'" in content:
                content = content.replace("'use client';", "'use client';\n\nimport { memo } from 'react';", 1)
            else:
                content = "import { memo } from 'react';\n" + content
    
    # Replace: export function ComponentName(...) {
    # With: export const ComponentName = memo(function ComponentName(...) {
    pattern = rf'export\s+function\s+{component_name}\s*\(([^)]*?)\)\s*\{{'
    match = re.search(pattern, content)
    if match:
        params = match.group(1)
        replacement = f'export const {component_name} = memo(function {component_name}({params}) {{'
        content = content[:match.start()] + replacement + content[match.end():]
        
        # Find the closing of the component and add closing paren for memo
        # We need to find the last closing brace that matches the function
        # Find the export at the end if any, or the last }
        # The component function's closing } needs to be followed by );
        
        # Find the end of the file - the last } should close the function
        # We need to add ); after the last }
        lines = content.rstrip().split('\n')
        # Find the last line that is just '}'
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == '}':
                lines[i] = lines[i] + ');'
                break
        content = '\n'.join(lines) + '\n'
    
    with open(filepath, 'w') as f:
        f.write(content)
    return True

def add_usememo_and_usecallback(filepath):
    """Add useMemo and useCallback to ProductList component."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add useMemo and useCallback to imports
    react_import = re.search(r"import\s*\{([^}]+)\}\s*from\s*['\"]react['\"];", content)
    if react_import:
        existing = react_import.group(1)
        imports_to_add = []
        if 'useMemo' not in existing:
            imports_to_add.append('useMemo')
        if 'useCallback' not in existing:
            imports_to_add.append('useCallback')
        if imports_to_add:
            new_import = f"import {{{existing}, {', '.join(imports_to_add)} }} from 'react';"
            content = content[:react_import.start()] + new_import + content[react_import.end():]
    
    # Wrap handleAddToCart in useCallback
    content = content.replace(
        'const handleAddToCart = (productId: string) => {\n    setCart(prev => [...prev, productId]);\n  };',
        'const handleAddToCart = useCallback((productId: string) => {\n    setCart(prev => [...prev, productId]);\n  }, []);'
    )
    
    # Wrap filteredProducts in useMemo
    old_filtered = """const filteredProducts = products
    .filter(p => p.name.toLowerCase().includes(filter.toLowerCase()))
    .filter(p => p.inStock)
    .sort((a, b) => sortBy === 'price' ? a.price - b.price : b.rating - a.rating);"""
    
    new_filtered = """const filteredProducts = useMemo(() => products
    .filter(p => p.name.toLowerCase().includes(filter.toLowerCase()))
    .filter(p => p.inStock)
    .sort((a, b) => sortBy === 'price' ? a.price - b.price : b.rating - a.rating), [products, filter, sortBy]);"""
    
    content = content.replace(old_filtered, new_filtered)
    
    # Wrap getReviewCount in useCallback
    content = content.replace(
        'const getReviewCount = (productId: string) => {\n    return reviews.filter(r => r.productId === productId).length;\n  };',
        'const getReviewCount = useCallback((productId: string) => {\n    return reviews.filter(r => r.productId === productId).length;\n  }, [reviews]);'
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    return True

def apply_render_fixes(product_card_path, product_list_path):
    """Apply all render optimization fixes."""
    wrap_component_in_memo(product_card_path, 'ProductCard')
    add_usememo_and_usecallback(product_list_path)
    return True
