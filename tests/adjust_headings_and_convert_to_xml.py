#!/usr/bin/env python3
"""
Script to adjust heading levels in a markdown file and convert to XML tree structure.
This script:
1. Reads the markdown file
2. Adjusts heading levels based on content relevance and hierarchy
3. Converts the adjusted markdown to XML tree structure
"""

import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
import html

def analyze_and_adjust_headings(content):
    """
    Analyze the current heading structure and adjust levels based on content relevance.
    """
    lines = content.split('\n')
    adjusted_lines = []
    
    for line in lines:
        # Check if line is a heading
        if line.strip().startswith('#'):
            heading_match = re.match(r'^(#+)\s*(.+)', line.strip())
            if heading_match:
                current_hashes = heading_match.group(1)
                heading_text = heading_match.group(2).strip()
                
                # Determine proper heading level based on content
                new_level = determine_heading_level(heading_text)
                new_hashes = '#' * new_level
                adjusted_lines.append(f"{new_hashes} {heading_text}")
            else:
                adjusted_lines.append(line)
        else:
            adjusted_lines.append(line)
    
    return '\n'.join(adjusted_lines)

def determine_heading_level(heading_text):
    """
    Determine the appropriate heading level based on content analysis.
    """
    # Remove any numbering to analyze the actual content
    clean_text = re.sub(r'^\d+(\.\d+)*\s*', '', heading_text).strip()
    
    # Main document sections (H1)
    main_sections = [
        'Mass Transit Railway Corporation',
        'Prerequisite and Safety',
        'Maintenance Concept', 
        'Tool list',
        'Portable Testing Equipment',
        'Description of Main Parts',
        'Preventive Maintenance',
        'Troubleshooting',
        'Corrective Maintenance'
    ]
    
    # Check for main sections
    for section in main_sections:
        if section.lower() in clean_text.lower() or clean_text.lower().startswith(section.lower()):
            return 1
    
    # If heading starts with single number (like "1 ", "2 ", etc.) - these are main sections
    if re.match(r'^\d+\s+[A-Z]', heading_text):
        return 1
    
    # If heading starts with number.number (like "1.1 ", "2.3 ", etc.) - these are subsections  
    if re.match(r'^\d+\.\d+\s+', heading_text):
        return 2
    
    # If heading starts with number.number.number (like "1.1.1 ", "2.3.4 ", etc.) - these are sub-subsections
    if re.match(r'^\d+\.\d+\.\d+\s+', heading_text):
        return 3
    
    # Special handling for specific content types
    if any(word in clean_text.lower() for word in ['general', 'introduction', 'overview']):
        # These are typically subsections
        return 2
    
    if any(word in clean_text.lower() for word in ['procedure', 'step', 'description of procedure']):
        # These are typically sub-subsections
        return 3
    
    if clean_text.lower().startswith('replace ') or clean_text.lower().startswith('adjust ') or clean_text.lower().startswith('installation'):
        # Maintenance procedures - subsections
        return 2
    
    if 'days check' in clean_text.lower() or 'maintenance' in clean_text.lower():
        # Maintenance sections
        return 2
    
    # Safety and warning sections
    if any(word in clean_text.lower() for word in ['safety', 'warning', 'danger', 'caution']):
        return 3
    
    # For anything else, try to infer from context
    # If it's a short phrase, likely a subsection
    if len(clean_text.split()) <= 4:
        return 2
    else:
        return 3

def markdown_to_xml_tree(markdown_content):
    """
    Convert markdown content to XML tree structure preserving hierarchy.
    """
    lines = markdown_content.split('\n')
    root = ET.Element('manual')
    root.set('title', 'Platform Screen Doors Maintenance Manual')
    
    current_section = None
    current_subsection = None
    current_subsubsection = None
    current_content = []
    
    for line in lines:
        # Check if line is a heading
        heading_match = re.match(r'^(#+)\s*(.+)', line.strip())
        
        if heading_match:
            # Save previous content if any
            if current_content:
                content_text = '\n'.join(current_content).strip()
                if content_text:
                    # Add content to the appropriate parent
                    if current_subsubsection is not None:
                        if current_subsubsection.text:
                            current_subsubsection.text += '\n' + escape_xml_content(content_text)
                        else:
                            current_subsubsection.text = escape_xml_content(content_text)
                    elif current_subsection is not None:
                        if current_subsection.text:
                            current_subsection.text += '\n' + escape_xml_content(content_text)
                        else:
                            current_subsection.text = escape_xml_content(content_text)
                    elif current_section is not None:
                        if current_section.text:
                            current_section.text += '\n' + escape_xml_content(content_text)
                        else:
                            current_section.text = escape_xml_content(content_text)
                    else:
                        # Add to root if no section
                        intro_elem = ET.SubElement(root, 'introduction')
                        intro_elem.text = escape_xml_content(content_text)
                
                current_content = []
            
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            
            if level == 1:
                # Main section
                current_section = ET.SubElement(root, 'section')
                current_section.set('title', escape_xml_content(heading_text))
                current_section.set('level', '1')
                current_subsection = None
                current_subsubsection = None
                
            elif level == 2:
                # Subsection
                if current_section is not None:
                    current_subsection = ET.SubElement(current_section, 'subsection')
                    current_subsection.set('title', escape_xml_content(heading_text))
                    current_subsection.set('level', '2')
                    current_subsubsection = None
                else:
                    # Create a section if none exists
                    current_section = ET.SubElement(root, 'section')
                    current_section.set('title', 'General')
                    current_section.set('level', '1')
                    current_subsection = ET.SubElement(current_section, 'subsection')
                    current_subsection.set('title', escape_xml_content(heading_text))
                    current_subsection.set('level', '2')
                    current_subsubsection = None
                    
            elif level == 3:
                # Sub-subsection
                if current_subsection is not None:
                    current_subsubsection = ET.SubElement(current_subsection, 'subsubsection')
                    current_subsubsection.set('title', escape_xml_content(heading_text))
                    current_subsubsection.set('level', '3')
                elif current_section is not None:
                    # Create a subsection if none exists
                    current_subsection = ET.SubElement(current_section, 'subsection')
                    current_subsection.set('title', 'General')
                    current_subsection.set('level', '2')
                    current_subsubsection = ET.SubElement(current_subsection, 'subsubsection')
                    current_subsubsection.set('title', escape_xml_content(heading_text))
                    current_subsubsection.set('level', '3')
                else:
                    # Create section and subsection if none exist
                    current_section = ET.SubElement(root, 'section')
                    current_section.set('title', 'General')
                    current_section.set('level', '1')
                    current_subsection = ET.SubElement(current_section, 'subsection')
                    current_subsection.set('title', 'General')
                    current_subsection.set('level', '2')
                    current_subsubsection = ET.SubElement(current_subsection, 'subsubsection')
                    current_subsubsection.set('title', escape_xml_content(heading_text))
                    current_subsubsection.set('level', '3')
                    
            else:
                # Level 4+ - treat as sub-sub-subsection content
                current_content.append(f"{'#' * level} {heading_text}")
        else:
            # Regular content line
            current_content.append(line)
    
    # Don't forget the last section's content
    if current_content:
        content_text = '\n'.join(current_content).strip()
        if content_text:
            if current_subsubsection is not None:
                if current_subsubsection.text:
                    current_subsubsection.text += '\n' + escape_xml_content(content_text)
                else:
                    current_subsubsection.text = escape_xml_content(content_text)
            elif current_subsection is not None:
                if current_subsection.text:
                    current_subsection.text += '\n' + escape_xml_content(content_text)
                else:
                    current_subsection.text = escape_xml_content(content_text)
            elif current_section is not None:
                if current_section.text:
                    current_section.text += '\n' + escape_xml_content(content_text)
                else:
                    current_section.text = escape_xml_content(content_text)
            else:
                # Add to root if no section
                conclusion_elem = ET.SubElement(root, 'conclusion')
                conclusion_elem.text = escape_xml_content(content_text)
    
    return root

def escape_xml_content(text):
    """
    Escape special characters in XML content.
    """
    if text is None:
        return ""
    # Use html.escape to handle XML special characters and also handle quotes
    escaped = html.escape(str(text), quote=True)
    # Additional escaping for XML-specific issues
    escaped = escaped.replace('\x00', '')  # Remove null characters
    escaped = escaped.replace('\x01', '')  # Remove control characters
    escaped = escaped.replace('\x02', '')
    escaped = escaped.replace('\x03', '')
    escaped = escaped.replace('\x04', '')
    escaped = escaped.replace('\x05', '')
    escaped = escaped.replace('\x06', '')
    escaped = escaped.replace('\x07', '')
    escaped = escaped.replace('\x08', '')
    # Remove other control characters (except \t, \n, \r)
    import re
    escaped = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', escaped)
    return escaped

def prettify_xml(elem):
    """
    Return a pretty-printed XML string for the Element.
    """
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def main():
    # File paths
    input_file = '/home/qiyue/mtr-v2/.data/result/manual/manual copy.md'
    output_markdown_file = '/home/qiyue/mtr-v2/.data/result/manual/manual_adjusted_headings.md'
    output_xml_file = '/home/qiyue/mtr-v2/.data/result/manual/manual.xml'
    
    print("Reading markdown file...")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("Analyzing and adjusting heading levels...")
    adjusted_content = analyze_and_adjust_headings(content)
    
    print("Saving adjusted markdown...")
    with open(output_markdown_file, 'w', encoding='utf-8') as f:
        f.write(adjusted_content)
    
    print("Converting to XML tree structure...")
    xml_root = markdown_to_xml_tree(adjusted_content)
    
    print("Saving XML file...")
    # Create XML string without pretty printing first to avoid encoding issues
    xml_string = ET.tostring(xml_root, encoding='unicode')
    
    with open(output_xml_file, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(xml_string)
    
    print(f"Process completed!")
    print(f"Adjusted markdown saved to: {output_markdown_file}")
    print(f"XML tree structure saved to: {output_xml_file}")
    
    # Print some statistics
    sections = len(xml_root.findall('section'))
    subsections = len(xml_root.findall('.//subsection'))
    subsubsections = len(xml_root.findall('.//subsubsection'))
    
    print(f"\nDocument structure:")
    print(f"- Main sections (H1): {sections}")
    print(f"- Subsections (H2): {subsections}")
    print(f"- Sub-subsections (H3): {subsubsections}")

if __name__ == "__main__":
    main()
