"""
LaTeX Resume Parser
Parses and modifies LaTeX resume while preserving exact formatting
"""

import re
import os

class LaTeXParser:
    """Parse and modify LaTeX resumes while preserving structure"""
    
    def __init__(self, tex_path):
        self.tex_path = tex_path
        with open(tex_path, 'r', encoding='utf-8') as f:
            self.content = f.read()
        
        # Track sections
        self.sections = self._extract_sections()
    
    def _extract_sections(self):
        """Extract all sections from LaTeX"""
        sections = {}
        section_pattern = r'\\section\{([^}]+)\}(.*?)(?=\\section\{|$)'
        
        for match in re.finditer(section_pattern, self.content, re.DOTALL):
            name = match.group(1).strip()
            content = match.group(2).strip()
            sections[name] = content
        
        return sections
    
    def get_experience_section(self):
        """Get experience entries"""
        exp = self.sections.get('EXPERIENCE', '')
        
        # Extract subheadings (jobs)
        jobs = []
        job_pattern = r'\\resumeSubheading\s*\{([^}]+)\}\s*\{([^}]+)\}\s*\{([^}]+)\}\s*\{([^}]+)\}'
        
        for match in re.finditer(job_pattern, exp):
            jobs.append({
                'company': match.group(1),
                'duration': match.group(2),
                'role': match.group(3),
                'location': match.group(4),
                'full_text': match.group(0)
            })
        
        return jobs
    
    def get_skills_section(self):
        """Extract skills"""
        return self.sections.get('SKILLS', '')
    
    def get_projects_section(self):
        """Extract projects"""
        return self.sections.get('PROJECTS', '')
    
    def replace_experience_item(self, company, new_description):
        """Replace experience item for a specific company"""
        # Find the job with this company
        job_pattern = f(r'\\resumeSubheading\s*\{{{re.escape(company)}\}}.*?{{.*?}}.*?{{.*?}}.*?{{.*?}}'
                        r'(.*?)(?=\\resumeSubheading|\resumeSubHeadingListEnd)', re.DOTALL)
        
        def replace_func(match):
            old_items = match.group(1)
            # Replace resumeItem content while keeping structure
            new_items = self._format_new_items(new_description)
            return match.group(0).replace(old_items, new_items)
        
        new_content = re.sub(job_pattern, replace_func, self.content, flags=re.DOTALL)
        self.content = new_content
    
    def _format_new_items(self, descriptions):
        """Format new bullet points keeping LaTeX structure"""
        items = []
        for desc in descriptions:
            if desc.strip():
                items.append(f"\\resumeItem{{{desc}}}")
        return '\n'.join(items)
    
    def add_skill(self, skill_category, new_skill):
        """Add a skill to a category"""
        pattern = rf'\\textbf\{{{skill_category}\}}\s*{{(.*?)}}'
        
        def replace_func(match):
            current = match.group(1).strip()
            if new_skill not in current:
                updated = current + f", {new_skill}"
                return match.group(0).replace(current, updated)
            return match.group(0)
        
        self.content = re.sub(pattern, replace_func, self.content)
    
    def save(self, output_path=None):
        """Save the modified LaTeX"""
        path = output_path or self.tex_path
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.content)
        return path
    
    def compile_pdf(self, output_dir=None):
        """Compile LaTeX to PDF"""
        from pathlib import Path
        
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Save current content to temp file
        temp_tex = self.tex_path.replace('.tex', '_temp.tex')
        with open(temp_tex, 'w', encoding='utf-8') as f:
            f.write(self.content)
        
        # Compile
        cmd = f'pdflatex -interaction=nonstopmode -output-directory="{output_dir or os.path.dirname(self.tex_path)}" "{temp_tex}"'
        result = os.system(cmd)
        
        # Clean up
        temp_base = temp_tex.replace('.tex', '')
        for ext in ['.aux', '.log', '.out']:
            try:
                os.remove(temp_base + ext)
            except:
                pass
        
        return result == 0


def parse_resume(tex_path):
    """Helper to quickly parse a resume"""
    return LaTeXParser(tex_path)