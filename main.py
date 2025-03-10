import os
import PyPDF2
import google.generativeai as genai
from pathlib import Path
from fpdf import FPDF
import re

def main():
    # Create necessary folders if they don't exist
    resume_folder = Path("resume")
    output_folder = Path("newresume")

    if not resume_folder.exists():
        os.makedirs(resume_folder)
        print(f"Created '{resume_folder}' folder. Please place your resume PDF there.")
        return

    if not output_folder.exists():
        os.makedirs(output_folder)

    # Get the first PDF file from the resume folder
    pdf_files = list(resume_folder.glob("*.pdf"))
    if not pdf_files:
        print("No PDF resume found in the 'resume' folder. Please add a resume.")
        return

    resume_path = pdf_files[0]
    print(f"Found resume: {resume_path.name}")

    # Get job description file
    job_desc_path = Path("job_description.txt")
    if not job_desc_path.exists():
        print("Job description file 'job_description.txt' not found. Please create this file with the job requirements.")
        return

    # Check for additional details file
    additional_details_path = Path("additional_details.txt")
    additional_details = ""
    if additional_details_path.exists():
        try:
            # Try UTF-8 first
            with open(additional_details_path, "r", encoding="utf-8") as file:
                additional_details = file.read()
            print("Found additional details file. This information will be incorporated into the resume.")
        except UnicodeDecodeError:
            # Fall back to latin-1 which can read any byte value
            with open(additional_details_path, "r", encoding="latin-1") as file:
                additional_details = file.read()
            print("Found additional details file (using alternate encoding). This information will be incorporated into the resume.")
    else:
        print("No 'additional_details.txt' file found. Only using existing resume content.")

    # Extract text and analyze structure from resume
    resume_text, resume_structure = extract_from_pdf(resume_path)
    if not resume_text:
        print("Failed to extract text from the resume.")
        return

    # Read job description
    with open(job_desc_path, "r", encoding="utf-8") as file:
        job_description = file.read()

    # Optimize resume using Google Gemini
    optimized_resume = optimize_resume_with_gemini(resume_text, resume_structure, job_description, additional_details)
    if not optimized_resume:
        print("Failed to optimize the resume.")
        return

    # Save as .tex file for LaTeX processing
    tex_path = output_folder / f"optimized_{resume_path.stem}.tex"
    with open(tex_path, "w", encoding="utf-8") as file:
        file.write(optimized_resume)

    print(f"Optimized resume saved to: {tex_path}")
    print("Resume optimization complete!")
    
    # Generate PDF from the optimized resume content using our built-in method
    pdf_path = create_pdf_resume(optimized_resume, output_folder / f"optimized_{resume_path.stem}.pdf")
    print(f"PDF preview created at: {pdf_path}")
    
    # Compile the .tex file to create a proper LaTeX PDF
    try:
        import subprocess
        print("Attempting to compile LaTeX file to PDF...")
        cmd = ["pdflatex", "-output-directory", str(output_folder), str(tex_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"LaTeX compilation successful. PDF created at: {output_folder}/optimized_{resume_path.stem}.pdf")
        else:
            print("LaTeX compilation had issues. Using basic PDF version instead.")
            print(f"Error details: {result.stderr}")
    except Exception as e:
        print(f"Could not compile LaTeX: {e}")
        print("Using basic PDF version instead.")

def extract_from_pdf(pdf_path):
    """Extract text from a PDF file and analyze its structure."""
    try:
        with open(pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"

            # Analyze resume structure (sections, formatting, etc.)
            structure = analyze_resume_structure(text)

            return text, structure
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None, None

def analyze_resume_structure(text):
    """Analyze the structure of the resume to preserve formatting."""
    structure = {
        "sections": [],
        "has_bullet_points": False,
        "has_tables": False,
        "indentation_style": "unknown"
    }

    # Look for common section headers
    common_sections = ["EXPERIENCE", "EDUCATION", "SKILLS", "PROJECTS", "CERTIFICATIONS", 
                       "SUMMARY", "OBJECTIVE", "CONTACT", "REFERENCES", "PUBLICATIONS"]

    for section in common_sections:
        if re.search(r'(?i)\b' + section + r'\b', text):
            structure["sections"].append(section)

    # Check for bullet points
    if re.search(r'[•●■◦○◘►▪▫▸▹◆]', text):
        structure["has_bullet_points"] = True

    # Check for potential table structures (multiple consecutive lines with similar patterns)
    table_pattern = re.findall(r'(.+)\n(.+)\n(.+)', text)
    if table_pattern and len(set(len(line.split()) for line in table_pattern[0])) <= 2:
        structure["has_tables"] = True

    # Try to determine indentation style
    if re.search(r'\n\s{2,}', text):
        structure["indentation_style"] = "spaces"
    elif re.search(r'\n\t', text):
        structure["indentation_style"] = "tabs"

    return structure

def optimize_resume_with_gemini(resume_text, resume_structure, job_description, additional_details):
    """Use Google Gemini API to optimize the resume based on job description and convert to LaTeX format."""
    try:
        # Get Google Gemini API key from environment variables
        api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            print("Error: GEMINI_API_KEY not found in environment variables.")
            print("Please add your Gemini API key using the Secrets tool.")
            return None

        # Configure the Gemini API
        genai.configure(api_key=api_key)

        # Create a detailed prompt for the Gemini API
        sections_str = ", ".join(resume_structure["sections"])

        # Extract name and contact information from resume_text
        name_match = re.search(r'^([A-Za-z\s]+)', resume_text)
        name = name_match.group(1).strip() if name_match else "Name"
        
        # Try to find email in the resume
        email_match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', resume_text)
        email = email_match.group(1) if email_match else "email@example.com"
        
        # Try to find LinkedIn and GitHub links
        linkedin_match = re.search(r'linkedin\.com/in/([a-zA-Z0-9_-]+)', resume_text)
        linkedin = linkedin_match.group(0) if linkedin_match else "linkedin.com/in/username"
        
        github_match = re.search(r'github\.com/([a-zA-Z0-9_-]+)', resume_text)
        github = github_match.group(0) if github_match else "github.com/username"

        prompt = f"""
        I need to optimize a resume for this job description and convert it to LaTeX format.

        JOB DESCRIPTION:
        {job_description}

        CURRENT RESUME CONTENT:
        {resume_text}

        ADDITIONAL DETAILS ABOUT THE PERSON (incorporate if relevant):
        {additional_details}

        RESUME STRUCTURE ANALYSIS:
        - Sections detected: {sections_str}
        - Uses bullet points: {"Yes" if resume_structure["has_bullet_points"] else "No"}
        - Contains tables: {"Yes" if resume_structure["has_tables"] else "No"}
        - Indentation style: {resume_structure["indentation_style"]}

        Convert this resume to the following LaTeX format and structure:

\begin{document}

%----------HEADING----------
% \begin{tabular*}{\textwidth}{l@{\extracolsep{\fill}}r}
%   \textbf{\href{http://sourabhbajaj.com/}{\Large Sourabh Bajaj}} & Email : \href{mailto:sourabh@sourabhbajaj.com}{sourabh@sourabhbajaj.com}\\
%   \href{http://sourabhbajaj.com/}{http://www.sourabhbajaj.com} & Mobile : +1-123-456-7890 \\
% \end{tabular*}

\begin{center}
    \textbf{\Huge \scshape Jake Ryan} \\ \vspace{1pt}
    \small 123-456-7890 $|$ \href{mailto:x@x.com}{\underline{jake@su.edu}} $|$ 
    \href{https://linkedin.com/in/...}{\underline{linkedin.com/in/jake}} $|$
    \href{https://github.com/...}{\underline{github.com/jake}}
\end{center}


%-----------EDUCATION-----------
\section{Education}
  \resumeSubHeadingListStart
    \resumeSubheading
      {Southwestern University}{Georgetown, TX}
      {Bachelor of Arts in Computer Science, Minor in Business}{Aug. 2018 -- May 2021}
    \resumeSubheading
      {Blinn College}{Bryan, TX}
      {Associate's in Liberal Arts}{Aug. 2014 -- May 2018}
  \resumeSubHeadingListEnd


%-----------EXPERIENCE-----------
\section{Experience}
  \resumeSubHeadingListStart

    \resumeSubheading
      {Undergraduate Research Assistant}{June 2020 -- Present}
      {Texas A\&M University}{College Station, TX}
      \resumeItemListStart
        \resumeItem{Developed a REST API using FastAPI and PostgreSQL to store data from learning management systems}
        \resumeItem{Developed a full-stack web application using Flask, React, PostgreSQL and Docker to analyze GitHub data}
        \resumeItem{Explored ways to visualize GitHub collaboration in a classroom setting}
      \resumeItemListEnd
      
% -----------Multiple Positions Heading-----------
%    \resumeSubSubheading
%     {Software Engineer I}{Oct 2014 - Sep 2016}
%     \resumeItemListStart
%        \resumeItem{Apache Beam}
%          {Apache Beam is a unified model for defining both batch and streaming data-parallel processing pipelines}
%     \resumeItemListEnd
%    \resumeSubHeadingListEnd
%-------------------------------------------

    \resumeSubheading
      {Information Technology Support Specialist}{Sep. 2018 -- Present}
      {Southwestern University}{Georgetown, TX}
      \resumeItemListStart
        \resumeItem{Communicate with managers to set up campus computers used on campus}
        \resumeItem{Assess and troubleshoot computer problems brought by students, faculty and staff}
        \resumeItem{Maintain upkeep of computers, classroom equipment, and 200 printers across campus}
    \resumeItemListEnd

    \resumeSubheading
      {Artificial Intelligence Research Assistant}{May 2019 -- July 2019}
      {Southwestern University}{Georgetown, TX}
      \resumeItemListStart
        \resumeItem{Explored methods to generate video game dungeons based off of \emph{The Legend of Zelda}}
        \resumeItem{Developed a game in Java to test the generated dungeons}
        \resumeItem{Contributed 50K+ lines of code to an established codebase via Git}
        \resumeItem{Conducted  a human subject study to determine which video game dungeon generation technique is enjoyable}
        \resumeItem{Wrote an 8-page paper and gave multiple presentations on-campus}
        \resumeItem{Presented virtually to the World Conference on Computational Intelligence}
      \resumeItemListEnd

  \resumeSubHeadingListEnd


%-----------PROJECTS-----------
\section{Projects}
    \resumeSubHeadingListStart
      \resumeProjectHeading
          {\textbf{Gitlytics} $|$ \emph{Python, Flask, React, PostgreSQL, Docker}}{June 2020 -- Present}
          \resumeItemListStart
            \resumeItem{Developed a full-stack web application using with Flask serving a REST API with React as the frontend}
            \resumeItem{Implemented GitHub OAuth to get data from user’s repositories}
            \resumeItem{Visualized GitHub data to show collaboration}
            \resumeItem{Used Celery and Redis for asynchronous tasks}
          \resumeItemListEnd
      \resumeProjectHeading
          {\textbf{Simple Paintball} $|$ \emph{Spigot API, Java, Maven, TravisCI, Git}}{May 2018 -- May 2020}
          \resumeItemListStart
            \resumeItem{Developed a Minecraft server plugin to entertain kids during free time for a previous job}
            \resumeItem{Published plugin to websites gaining 2K+ downloads and an average 4.5/5-star review}
            \resumeItem{Implemented continuous delivery using TravisCI to build the plugin upon new a release}
            \resumeItem{Collaborated with Minecraft server administrators to suggest features and get feedback about the plugin}
          \resumeItemListEnd
    \resumeSubHeadingListEnd



%
%-----------PROGRAMMING SKILLS-----------
\section{Technical Skills}
 \begin{itemize}[leftmargin=0.15in, label={}]
    \small{\item{
     \textbf{Languages}{: Java, Python, C/C++, SQL (Postgres), JavaScript, HTML/CSS, R} \\
     \textbf{Frameworks}{: React, Node.js, Flask, JUnit, WordPress, Material-UI, FastAPI} \\
     \textbf{Developer Tools}{: Git, Docker, TravisCI, Google Cloud Platform, VS Code, Visual Studio, PyCharm, IntelliJ, Eclipse} \\
     \textbf{Libraries}{: pandas, NumPy, Matplotlib}
    }}
 \end{itemize}


%-------------------------------------------
\end{document}

        Fill in all the sections with the optimized content from the original resume. 
        Make sure to:
        1. Format the resume to match the exact LaTeX structure shown above
        2. Extract and optimize the content from the original resume
        3. Match keywords and phrases from the job description
        4. Highlight skills and experiences that align with the job requirements
        5. Focus on achievements and metrics relevant to the position
        6. Use powerful action verbs and quantifiable achievements
        7. Include ALL sections from the LaTeX template, filling them with appropriate content

        Return ONLY the LaTeX code for the resume. Do not include any explanations or markdown.
        """

        # Get available models
        model = genai.GenerativeModel('gemini-2.0-flash')

        # Generate content
        response = model.generate_content(prompt)

        # Extract and return the optimized resume
        return response.text

    except Exception as e:
        print(f"Error with Google Gemini API: {e}")
        return None

def create_pdf_resume(content, output_path):
    """Convert the optimized LaTeX resume content to a properly formatted PDF."""
    try:
        # Save the LaTeX content to a .tex file with the same path structure if not already saved
        if '.tex' not in str(output_path):
            tex_path = str(output_path).replace('.pdf', '.tex')
            with open(tex_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
        # Create a basic PDF that follows the LaTeX structure
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Set margins to match LaTeX style
        pdf.set_margins(15, 15, 15)
        
        # Define fonts and sizes
        header_font = "Arial"
        body_font = "Arial"
        
        # Parse LaTeX content
        # Extract name
        name_match = re.search(r'\\textbf{\\Huge \\scshape ([^}]+)}', content)
        name = name_match.group(1) if name_match else "Name"
        
        # Extract contact info
        contact_match = re.search(r'\\small ([^\n]+)', content)
        contact = contact_match.group(1) if contact_match else ""
        contact = re.sub(r'\\href{[^}]+}{\\underline{([^}]+)}}', r'\1', contact)
        contact = contact.replace('$|$', '|')
        
        # Set name at top
        pdf.set_font(header_font, 'B', 16)
        pdf.cell(0, 10, name, 0, 1, 'C')
        
        # Set contact info
        pdf.set_font(body_font, '', 10)
        pdf.cell(0, 6, contact, 0, 1, 'C')
        pdf.ln(4)
        
        # Process sections
        section_pattern = r'\\section{([^}]+)}(.*?)(?=\\section{|\\end{document})'
        for match in re.finditer(section_pattern, content, re.DOTALL):
            section_title = match.group(1)
            section_content = match.group(2)
            
            # Add section title
            pdf.set_font(header_font, 'B', 14)
            pdf.cell(0, 10, section_title, 0, 1, 'L')
            pdf.ln(1)
            
            # Draw horizontal line
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(4)
            
            # Extract \resumeSubheading blocks
            subheading_pattern = r'\\resumeSubheading\s*{([^}]*)}{([^}]*)}{([^}]*)}{([^}]*)}'
            for subheading_match in re.finditer(subheading_pattern, section_content):
                org = subheading_match.group(1)
                location = subheading_match.group(2)
                title = subheading_match.group(3)
                date = subheading_match.group(4)
                
                # Add organization and location
                pdf.set_font(body_font, 'B', 11)
                pdf.cell(120, 6, org, 0, 0, 'L')
                pdf.cell(60, 6, location, 0, 1, 'R')
                
                # Add title and date
                pdf.set_font(body_font, 'I', 10)
                pdf.cell(120, 6, title, 0, 0, 'L')
                pdf.cell(60, 6, date, 0, 1, 'R')
                pdf.ln(2)
            
            # Extract \resumeProjectHeading blocks
            project_pattern = r'\\resumeProjectHeading\s*{([^}]*)}{([^}]*)}'
            for project_match in re.finditer(project_pattern, section_content):
                project_info = project_match.group(1)
                project_date = project_match.group(2)
                
                # Clean up LaTeX formatting for project info
                project_info = re.sub(r'\\textbf{([^}]*)}', r'\1', project_info)
                project_info = re.sub(r'\\emph{([^}]*)}', r'\1', project_info)
                
                # Add project info and date
                pdf.set_font(body_font, 'B', 11)
                pdf.cell(120, 6, project_info, 0, 0, 'L')
                pdf.cell(60, 6, project_date, 0, 1, 'R')
                pdf.ln(2)
            
            # Extract bullet points
            bullet_pattern = r'\\resumeItem{([^}]*)}'
            for bullet_match in re.finditer(bullet_pattern, section_content):
                bullet_text = bullet_match.group(1)
                
                # Add bullet point
                pdf.set_font(body_font, '', 10)
                pdf.cell(5, 6, "•", 0, 0, 'L')
                pdf.multi_cell(175, 6, bullet_text, 0, 'L')
            
            # Handle technical skills section specially
            if section_title == "Technical Skills":
                skills_pattern = r'\\textbf{([^}]*)}{{: ([^}\\]*)}}'
                for skills_match in re.finditer(skills_pattern, section_content):
                    skill_category = skills_match.group(1)
                    skill_list = skills_match.group(2)
                    
                    pdf.set_font(body_font, 'B', 10)
                    pdf.cell(30, 6, skill_category + ":", 0, 0, 'L')
                    pdf.set_font(body_font, '', 10)
                    pdf.multi_cell(150, 6, skill_list, 0, 'L')
            
            pdf.ln(5)  # Space between sections
        
        # Save the PDF
        pdf.output(str(output_path))
        return output_path

    except Exception as e:
        print(f"Error creating PDF: {e}")
        return None

if __name__ == "__main__":
    main()