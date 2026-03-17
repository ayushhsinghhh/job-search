"""
Resume Tailoring Prompts
Keeps the same style and tone: impact -> what and how
"""

SYSTEM_PROMPT = """You are an expert resume tailor. You modify resumes to match job descriptions while:
1. Preserving the exact LaTeX structure and formatting
2. Maintaining the IMPACT-DRIVEN style: What happened + How you did it
3. Using the same tone - professional, concise, metrics-focused
4. Keeping bullet points that show:
   - WHAT: The task/challenge
   - HOW: The specific action/technology used
   - RESULT: Quantified impact with metrics

Example format to maintain:
\\resumeItem{Built \\textbf{Enrichment Agent} that parses \\textbf{BS, IS, and CF statements} into structured spreadsheets --- \\textbf{matched 3 credit analysts across 12 companies} —- exact revenue extraction, \\textbf{<2\\% deviation} on EBITDA, Debt, and Liquidity}

Key rules:
- Keep \\textbf{} for key technologies and metrics
- Use --- to separate the action from the impact
- Always include quantified metrics when possible
- Match the job's required skills by highlighting relevant experience
- Keep the same bullet point structure"""


def create_tailor_prompt(job_title, job_company, job_description, current_resume):
    """Create prompt for tailoring resume to a job"""
    
    prompt = f"""Current LaTeX Resume (EXPERIENCE section only):

{current_resume}

---

Job to apply for:
- Title: {job_title}
- Company: {job_company}
- Description: {job_description[:2000]}

---

Task:
1. Read the job description carefully
2. Identify key skills/requirements
3. Modify the EXPERIENCE section to:
   - Highlight experiences most relevant to this job
   - Use similar keywords from the job description
   - Reorder bullet points to put most relevant items first
   - Add or emphasize skills that match the job

4. IMPORTANT: Keep the EXACT same LaTeX commands:
   - \\resumeSubheading{{Company}}{{Duration}}{{Role}}{{Location}}
   - \\resumeItemListStart / \\resumeItemListEnd
   - \\resumeItem{{Your bullet point text}}

5. Keep the same IMPACT style:
   - Use \\textbf{{}} for key technologies and metrics
   - Use --- to separate action from impact
   - Include quantified results

Return ONLY the modified EXPERIENCE section LaTeX code.
Start with \\section{{EXPERIENCE}} and end with \\resumeSubHeadingListEnd"""

    return prompt


def create_skills_prompt(job_description, current_skills):
    """Create prompt for suggesting skills to add"""
    
    prompt = f"""Current Skills section:

{current_skills}

---

Job Description (extract key skills):

{job_description[:1500]}

---

Task:
Identify skills from the job description that are NOT in the current resume.
Return ONLY a comma-separated list of new skills to add, in the same format as the original.
If nothing to add, return "NONE"."""

    return prompt


# Style guide to maintain consistency
STYLE_GUIDE = """
LaTeX Resume Style Guide:
- Use \\resumeItem{{text}} for bullet points
- Use \\textbf{{key term}} for technologies and metrics
- Use --- to separate action from impact
- Keep bullet points under 2 lines
- Use specific metrics: %, $, 10x, etc.
- Example: Built {Enrichment Agent} that parses {BS, IS, CF statements} --- {matched 3 credit analysts} --- {<2% deviation}
"""