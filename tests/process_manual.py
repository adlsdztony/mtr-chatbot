#!/usr/bin/env python3
"""
Script to process the manual markdown file:
1. Adjust heading levels based on content hierarchy
2. Convert to XML tree structure
"""

import re
import xml.etree.ElementTree as ET

def read_markdown_file(filepath):
    """Read the markdown file and return its content."""
    with open(filepath, 'r', encoding='utf-8') as file:
        return file.read()

def analyze_heading_structure(content):
    """Analyze the content to determine appropriate heading levels."""
    lines = content.split('\n')
    processed_lines = []
    
    for line in lines:
        if line.startswith('# '):
            heading_text = line[2:].strip()
            
            # Determine heading level based on content patterns
            level = determine_heading_level(heading_text)
            
            # Replace with appropriate heading level
            processed_lines.append('#' * level + ' ' + heading_text)
        else:
            processed_lines.append(line)
    
    return '\n'.join(processed_lines)

def determine_heading_level(heading_text):
    """Determine the appropriate heading level based on the content."""
    
    # Main document title
    if heading_text == "Mass Transit Railway Corporation":
        return 1
    
    # Main numbered sections (1, 2, 3, etc.)
    if re.match(r'^\d+\s+', heading_text):
        return 1
    
    # Subsections with decimal numbering (1.1, 2.3, etc.)
    if re.match(r'^\d+\.\d+\s+', heading_text):
        return 2
    
    # Sub-subsections with three-level numbering (1.1.1, 2.3.4, etc.)
    if re.match(r'^\d+\.\d+\.\d+\s+', heading_text):
        return 3
    
    # Four-level numbering
    if re.match(r'^\d+\.\d+\.\d+\.\d+\s+', heading_text):
        return 4
    
    # Special patterns for procedure steps
    if any(keyword in heading_text.lower() for keyword in ['disassembly:', 'assembly:', 'description of procedure:', 'task:', 'remove', 'install', 'replace']):
        return 3
    
    # Check for procedural headings that end with ":"
    if heading_text.endswith(':'):
        return 3
    
    # Technical component names or specific procedures
    if any(keyword in heading_text for keyword in ['DCU', 'PSD', 'Drive Unit', 'Motor', 'Safety', 'Power Distribution', 'Locking Block', 'Hazard Detector']):
        return 2
    
    # Default for other headings
    return 2

def markdown_to_xml(markdown_content):
    """Convert markdown content to XML tree structure."""
    lines = markdown_content.split('\n')
    root = ET.Element('manual')
    current_path = [root]  # Stack to track current nesting level
    current_text = []  # Accumulate text content
    
    def add_text_to_current_node():
        """Add accumulated text to the current node."""
        if current_text:
            text_content = '\n'.join(current_text).strip()
            if text_content:
                # Escape special XML characters
                text_content = escape_xml_text(text_content)
                # Remove any existing text and set new text
                if current_path[-1].text:
                    current_path[-1].text = current_path[-1].text.strip() + '\n' + text_content
                else:
                    current_path[-1].text = text_content
            current_text.clear()
    
    for line in lines:
        line = line.rstrip()
        
        # Check if line is a heading
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            # Add any accumulated text to current node
            add_text_to_current_node()
            
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            
            # Adjust current path based on heading level
            # Keep only the nodes up to the parent level
            target_depth = level  # 1-based level becomes target depth
            current_path = current_path[:target_depth]
            
            # Create new node for this heading
            # Create a valid XML tag name from heading text
            tag_name = create_xml_tag_name(heading_text)
            new_node = ET.SubElement(current_path[-1], tag_name)
            new_node.set('title', escape_xml_text(heading_text))
            new_node.set('level', str(level))
            
            # Add to current path
            current_path.append(new_node)
        else:
            # Regular content line
            if line.strip():  # Only add non-empty lines
                current_text.append(line)
    
    # Add any remaining text
    add_text_to_current_node()
    
    return root

def create_xml_tag_name(heading_text):
    """Create a valid XML tag name from heading text."""
    # Remove special characters and replace with underscores
    tag_name = re.sub(r'[^\w\s-]', '', heading_text)
    tag_name = re.sub(r'\s+', '_', tag_name.strip())
    tag_name = tag_name.lower()
    
    # Ensure it starts with a letter or underscore
    if tag_name and not (tag_name[0].isalpha() or tag_name[0] == '_'):
        tag_name = 'section_' + tag_name
    
    # Limit length and handle empty names
    if not tag_name or len(tag_name) > 50:
        tag_name = 'section'
    
    return tag_name

def escape_xml_text(text):
    """Escape special characters in XML text content."""
    if not text:
        return text
    
    # Replace XML special characters
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    
    return text


def save_adjusted_markdown(content, filepath):
    """Save the adjusted markdown content to a file."""
    with open(filepath, 'w', encoding='utf-8') as file:
        file.write(content)

def save_xml(xml_root, filepath):
    """Save the XML tree to a file."""
    # Use ElementTree's built-in formatting instead of minidom
    ET.indent(xml_root, space="  ", level=0)
    tree = ET.ElementTree(xml_root)
    tree.write(filepath, encoding='utf-8', xml_declaration=True)

def main():
    """Main processing function."""
    input_file = '/home/qiyue/mtr-v2/.data/result/manual/manual copy.md'
    output_markdown_file = '/home/qiyue/mtr-v2/.data/result/manual/manual_adjusted.md'
    output_xml_file = '/home/qiyue/mtr-v2/.data/result/manual/manual.xml'
    
    print("Reading markdown file...")
    markdown_content = read_markdown_file(input_file)
    
    print("Analyzing and adjusting heading structure...")
    adjusted_content = analyze_heading_structure(markdown_content)
    
    print("Saving adjusted markdown...")
    save_adjusted_markdown(adjusted_content, output_markdown_file)
    
    print("Converting to XML...")
    xml_root = markdown_to_xml(adjusted_content)
    
    print("Saving XML file...")
    save_xml(xml_root, output_xml_file)
    
    print(f"Processing complete!")
    print(f"Adjusted markdown saved to: {output_markdown_file}")
    print(f"XML file saved to: {output_xml_file}")

if __name__ == "__main__":
    main()
