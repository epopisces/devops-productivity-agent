# Knowledge Ingestion Agent Prompt
> GitHub Copilot -> Claude Opus 4.5

Let's create the Knowledge Ingestion Agent.  It is a tool with the core function of updating the following knowledge sources listed in the PRD
- **Instructions File**: Local file with high-level org context summaries
- **Org URL Index**: Index of org-relevant URLs with metadata (domain of knowledge, context, content summary)
- **User Notes Files**: Local markdown files with frontmatter (both agent and user-generated)
    - **User Notes Index**: Index of Local markdown files with metadata (domain of knowledge, context, content summary)
- **Future**: Vector database for mature RAG implementation

It should store information in the appropriate formats (converting the incoming data to the appropriate format if necessary).

It should support a Confidence and Relevance score passed along with the content, and be capable of pausing (human-in-the-loop) to prompt the user to review/validate before committing if the confidence or relevance scores are below a certain threshold (the threshold should be stored in a config file).  Let me know if this isn't a supported feature of agent-as-tool in the framework.

The locations of the User Notes Index should be a configurable and stored in a config file in a dictionary of key/value pairs, with topic as the top level key and key value pairs for directory path, template file location, and any other useful information for processing.  This dictionary should be initially configured with just the key of 'default' with a directory path pointing to a project subdirectory named 'notes', and a generic template including sensible frontmatter defaults for quick agent reference to enable agent decisionmaking around degree of ingestion.

I'm open to other suggestions in meeting the knowledge sources goals.  Including metadata for the indexes, etc.

2026.02.13
I think I want to move into a more structured workflow.  Here is what I am envisioning:

- The user submits text or an image.
- The initial interaction determines whether the user is submitting information for ingestion, asking a question, or both.
- If a question is involved
  - determine what knowledge domain and tags are relevant
  - Perform a lookup on indexed knowledge sources based on domain and tag (reference links like URLs, or notes), retrieving summaries from those that match
  - the user should have the option to view those file(s)/reference(s) (open a link, etc), sorted by confidence
  - if the question can be answered from the sources with a high degree of confidence, the answer should be displayed
  - if the question can't be answered from the sources, the agent should ask the user if it should perform a web search
- if ingestion is involved
  - - determine what knowledge domain and tags are relevant
  - Perform a lookup on indexed knowledge sources based on domain and tag (reference links like URLs, or notes), retrieving summaries from those that match
  - the user should have the option to view those file(s)/reference(s) (open a link, etc), sorted by confidence
  - the agent should show the user a preview of the changes it would make to an existing file, or the content of the new file it will create

  All with the Microsoft Agent Framework.  What is your recommended flow for this (what should be an agent, an agent-as-tool, or simply Python functions as tools, and what workflow(s) should be involved)?
