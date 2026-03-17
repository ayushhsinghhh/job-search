# Job Automation

Automated job scraping and resume tailoring system.

## Structure

- `base_resume/` - LaTeX resume template
- `src/scraper/` - Job scraping module
- `src/tailor/` - Resume tailoring module

## Setup

```bash
conda create -n job-automation python=3.10
conda activate job-automation
pip install -r requirements.txt
```

Add MiKTeX to PATH for PDF compilation:
```
C:\Users\ayush\AppData\Local\Programs\MiKTeX\miktex\bin\x64
```