"""
A script to scan the stonecutter block in settings.gradle.kts to extract all version+loader
combinations as the subproject list, then output a json as the github action include matrix
"""
__author__ = 'Fallen_Breath'
# edit Skidam

import json
import os
import re
import sys


def parse_subprojects() -> list[str]:
    """Parse the stonecutter match() calls in settings.gradle.kts to extract subproject names"""
    settings_path = 'settings.gradle.kts'

    if not os.path.isfile(settings_path):
        print(f"Error: '{settings_path}' not found", file=sys.stderr)
        sys.exit(1)

    with open(settings_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract all match("version", "loader1", "loader2", ...) calls
    # Pattern: match("X.Y", "loader1", "loader2")
    match_pattern = r'match\s*\(\s*"([^"]+)"\s*,\s*((?:"[^"]+"\s*,?\s*)+)\s*\)'
    subprojects = []

    for match in re.finditer(match_pattern, content):
        version = match.group(1)
        loaders_str = match.group(2)
        loaders = re.findall(r'"([^"]+)"', loaders_str)
        for loader in loaders:
            subprojects.append(f'{version}-{loader}')

    # Remove duplicates while preserving order
    seen = set()
    unique_subprojects = []
    for sp in subprojects:
        if sp not in seen:
            seen.add(sp)
            unique_subprojects.append(sp)

    return unique_subprojects


def parse_stonecutter_properties(path: str) -> dict[str, str]:
    """Parse stonecutter.properties.toml to extract publish_versions per Minecraft version.
    
    Returns a dict mapping version key (e.g. '1.21.1') to publish_versions string.
    """
    publish_versions = {}

    if not os.path.isfile(path):
        print(f"Warning: '{path}' not found, publish_versions will be empty", file=sys.stderr)
        return publish_versions

    current_section = None
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Match section headers like ["1.21.1"] or ["26.2"]
            section_match = re.match(r'^\["?([^"\]]+)"?\]$', line)
            if section_match:
                current_section = section_match.group(1)
                continue
            if current_section:
                kv_match = re.match(r'^(\w+)\s*=\s*"(.+)"$', line)
                if kv_match and kv_match.group(1) == 'publish_versions':
                    # Handle TOML escape sequences
                    value = kv_match.group(2)
                    value = value.replace('\\n', '\n')
                    value = value.replace('\\t', '\t')
                    value = value.replace('\\\\', '\\')
                    value = value.replace('\\"', '"')
                    publish_versions[current_section] = value

    return publish_versions


def main():
    target_subproject_env = os.environ.get('TARGET_SUBPROJECT', '')
    target_subprojects = list(filter(None, target_subproject_env.split(',') if target_subproject_env != '' else []))
    print(f'target_subprojects: {target_subprojects}')

    all_subprojects = parse_subprojects()
    print(f'found subprojects: {all_subprojects}')

    # Parse publish_versions from stonecutter.properties.toml
    publish_versions_map = parse_stonecutter_properties('stonecutter.properties.toml')
    print(f'publish_versions map: {publish_versions_map}')

    if len(target_subprojects) == 0:
        subprojects = all_subprojects
    else:
        subprojects = []
        for sp in all_subprojects:
            if sp in target_subprojects:
                subprojects.append(sp)
                target_subprojects.remove(sp)
        if len(target_subprojects) > 0:
            print(f'Unexpected subprojects: {target_subprojects}', file=sys.stderr)
            sys.exit(1)

    matrix_entries = []
    for subproject in subprojects:
        mc_version = subproject.split('-')[0]
        mod_brand = subproject.split('-')[1]
        # Look up publish_versions by MC version; fall back to mc_version itself
        pub_versions = publish_versions_map.get(mc_version, mc_version)
        matrix_entries.append({
            'subproject': subproject,
            'mod_brand': mod_brand,
            'mc_version': mc_version,
            'publish_versions': pub_versions,
        })

    matrix = {'include': matrix_entries}

    with open(os.environ['GITHUB_OUTPUT'], 'w') as f:
        f.write(f'matrix={json.dumps(matrix)}\n')

    print('matrix:')
    print(json.dumps(matrix, indent=2))


if __name__ == '__main__':
    main()
