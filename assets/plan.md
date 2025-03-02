This plan describes how to build a software agent that checks out a repository, analyzes issues, and automatically applies fixes.

First, we ask the model to define the necessary tools based on the issue type. Next, we build these tools and instruct the model to use them to generate patches. If the defined tools are insufficient, we prompt the model to suggest alternatives or additional tools.

We manually run this process step by step (cell by cell) until the model successfully generates patches. This approach ensures that the model can produce patches while allowing us recognize the lack of sufficient tools to refine the tools or enhance the system prompt by providing more metadata.

---

### **Step 1: Define Required Tools**  
- Ask an LLM to determine the necessary tools based on the issue type.  
- Output: A list of tools required to address the issue.

```
You are an advanced software agent specializing in analyzing software repository issues and determining the necessary tools to resolve them.
 Provide only relevant tools and include a brief explanation of how each tool contributes to the solution.
```

---

### **Step 2: Build or Configure Tools**  
- Build the required tools.  
- If the tools are insufficient, ask the LLM to suggest alternatives or additional tools.  
- Output: A list of built tools.


```
You are a software automation agent tasked with configuring and utilizing the necessary tools to resolve a repository issue.
 Given a list of required tools, your goal is to apply them effectively to fix the issue.
 If the available tools are insufficient, identify additional tools, suggest alternatives, and justify their necessity.
```

---

### **Step 3: Generate and Apply Fixes**  
- Ask the LLM to use the defined tools to generate patches based on the issue description and repository context.  
- Output: Patches to be applied to the repository.  

```
You are an advanced software agent responsible for generating patches to fix repository issues using predefined tools and repository context.
 Given an issue description and a list of available tools, produce a patch file with the necessary code changes.   
```