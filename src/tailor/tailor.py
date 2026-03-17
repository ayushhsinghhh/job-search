"""
Resume Tailoring Agent
Uses Groq LLaMA to tailor resume to job descriptions
"""

import os
import re
import json
import subprocess
from datetime import datetime

try:
    import groq
except ImportError:
    print("Installing groq...")
    subprocess.run(["pip", "install", "groq"], check=True)
    import groq

from .latex_parser import LaTeXParser
from .prompts import SYSTEM_PROMPT, create_tailor_prompt

# Groq configuration - set GROQ_API_KEY environment variable or use .env.local
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Try loading from .env.local if not set
if not GROQ_API_KEY:
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env.local")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    if key == "GROQ_API_KEY":
                        GROQ_API_KEY = val
                        break
MODEL = "llama-3.3-70b-versatile"


class ResumeTailor:
    """Tailor resumes to job descriptions using Groq"""

    def __init__(self, api_key=None):
        self.client = groq.Groq(api_key=api_key or GROQ_API_KEY)
        self.model = MODEL
        self.tailored_count = 0

    def tailor(
        self, job_title, job_company, job_description, base_resume_path, output_dir
    ):
        """
        Tailor resume for a specific job

        Args:
            job_title: Job title
            job_company: Company name
            job_description: Full job description
            base_resume_path: Path to base LaTeX resume
            output_dir: Where to save tailored resume

        Returns:
            Path to tailored PDF
        """
        print(f"\n[Tailoring resume for: {job_title} @ {job_company}]")

        # Parse the base resume
        parser = LaTeXParser(base_resume_path)

        # Get current experience section
        current_exp = parser.sections.get("EXPERIENCE", "")

        # Create prompt
        prompt = create_tailor_prompt(
            job_title, job_company, job_description, current_exp
        )

        # Call Groq
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        tailored_experience = response.choices[0].message.content
        print(f"  [OK] LLM tailored experience section")

        # Replace experience section in LaTeX
        parser = self._replace_experience(parser, tailored_experience)

        # Create output filename
        safe_company = "".join(
            c for c in job_company if c.isalnum() or c in " -"
        ).strip()
        safe_title = "".join(c for c in job_title if c.isalnum() or c in " -").strip()[
            :20
        ]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        output_tex = os.path.join(
            output_dir, f"{safe_company}_{safe_title}_{timestamp}.tex"
        )
        os.makedirs(output_dir, exist_ok=True)

        # Save LaTeX
        parser.save(output_tex)

        # Compile PDF
        pdf_path = self._compile_latex(output_tex, output_dir)

        self.tailored_count += 1

        return pdf_path

    @staticmethod
    def _escape_latex(text):
        """Escape special characters that break LaTeX compilation"""
        # Don't escape characters that are part of LaTeX commands
        # Process line by line, only escape in non-command text
        result = []
        for line in text.split('\n'):
            # Skip lines that are LaTeX commands (start with \)
            # For each line, escape special chars that aren't already escaped
            # and aren't part of LaTeX commands like \resumeItem{...}
            # We escape: % _ & # $ ~
            # But NOT \ { } which are structural LaTeX
            for char, escaped in [('%', r'\%'), ('_', r'\_'), ('&', r'\&'),
                                   ('#', r'\#'), ('$', r'\$'), ('~', '\\textasciitilde{}')]:
                # Don't double-escape (if already escaped, skip)
                # Replace unescaped occurrences only
                line = re.sub(r'(?<!\\)' + re.escape(char), lambda m: escaped, line)
            result.append(line)
        return '\n'.join(result)

    def _replace_experience(self, parser, new_experience):
        """Replace experience section with tailored version"""
        new_experience = self._escape_latex(new_experience)
        # Find the EXPERIENCE section start and the next section after it
        # Match from \section{EXPERIENCE} to the next \section{ or \end{document}
        exp_section_match = re.search(
            r"(\\section\{EXPERIENCE\}.*?)(?=\\section\{|\n\\end\{document\})",
            parser.content,
            re.DOTALL,
        )

        if exp_section_match:
            # Find what comes after the EXPERIENCE section (SKILLS, PROJECTS, etc.)
            after_exp = parser.content[exp_section_match.end() :]

            # Replace just the experience section content
            parser.content = (
                parser.content[: exp_section_match.start()]
                + "\\section{EXPERIENCE}\n"
                + new_experience.strip()
                + "\n"
                + after_exp
            )

        return parser
        # Get everything after EXPERIENCE section (SKILLS, PROJECTS, etc.)
        after_match = re.search(
            r"\\resumeSubHeadingListEnd\s*(.*)\\end\{document\}",
            parser.content,
            re.DOTALL,
        )

        if header_match and after_match:
            header = header_match.group(1)
            after = after_match.group(1)
            parser.content = (
                header
                + "\\section{EXPERIENCE}\n"
                + new_experience
                + "\n"
                + after
                + "\n\\end{document}"
            )

        return parser

    def _compile_latex(self, tex_path, output_dir):
        """Compile LaTeX to PDF"""
        # Get MiKTeX path
        miktex_path = r"C:\Users\ayush\AppData\Local\Programs\MiKTeX\miktex\bin\x64"
        pdflatex_path = os.path.join(miktex_path, "pdflatex.exe")

        # Set up environment - add MiKTeX to PATH
        env = os.environ.copy()
        env["PATH"] = miktex_path + os.pathsep + env.get("PATH", "")

        # Compile twice for references
        result = None
        for _ in range(2):
            result = subprocess.run(
                [
                    pdflatex_path,
                    "-interaction=nonstopmode",
                    "-output-directory",
                    output_dir,
                    tex_path,
                ],
                env=env,
                capture_output=True,
                text=True,
            )

        # Return PDF path
        pdf_path = tex_path.replace(".tex", ".pdf")

        if os.path.exists(pdf_path):
            print(f"  [PDF] Compiled: {pdf_path}")
            return pdf_path
        else:
            print(f"  [ERROR] PDF compilation failed")
            if result:
                print(result.stdout[-500:] if result.stdout else "")
            return None


def tailor_resume(job_info, base_resume, output_dir):
    """
    Convenience function to tailor a resume

    Args:
        job_info: dict with 'title', 'company', 'description', 'url'
        base_resume: path to base LaTeX resume
        output_dir: directory to save tailored resumes

    Returns:
        path to tailored PDF
    """
    tailor = ResumeTailor()

    return tailor.tailor(
        job_title=job_info.get("title", ""),
        job_company=job_info.get("company", ""),
        job_description=job_info.get("description", ""),
        base_resume_path=base_resume,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    # Test
    BASE_RESUME = r"D:\acc\job-automation\base_resume\base_resume.tex"
    OUTPUT_DIR = r"D:\acc\applications"

    test_job = {
        "title": "Senior Data Engineer",
        "company": "Stripe",
        "description": "Looking for a data engineer with experience in Python, SQL, Spark, and building data pipelines. Experience with financial data is a plus.",
    }

    result = tailor_resume(test_job, BASE_RESUME, OUTPUT_DIR)
    print(f"\n[DONE] Tailored resume: {result}")
