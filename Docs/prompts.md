Prompts 1 

Thoroughly review plan.md and assignment.md. Based on these documents, create a detailed implementation plan that:

- Covers all functional and non-functional requirements
- Breaks the project into clear phases and milestones
- Identifies key components, dependencies, and data flow
- Highlights risks, assumptions, and edge cases
- Specifies APIs, data models, and processing pipelines
- Includes a step-by-step execution strategy

If any requirement or detail is unclear, ask targeted clarification questions before proceeding.

Prompt 2: 

Prompt:

Write clean, modular, and well-documented code with the following standards:

Backend (FastAPI)
Use FastAPI with clear separation of:
Routing (HTTP handlers)
Business logic (services)
Data models (schemas)
Apply:
Type hints everywhere
Constants for configuration values
Dependency injection where appropriate
Include:
Docstrings for all functions/classes
Inline comments for non-obvious logic
Frontend (Vite + React)
Use React with Vite
Follow:
Component-based architecture
Separation of UI, state, and API logic
Ensure:
Reusable components
Clean folder structure
Proper state management (hooks or context)
General Principles
Avoid monolithic files
Use descriptive naming conventions
Keep code readable and scalable
Maintain consistency across the project

Prompt 3:

Implement Phase 1: Backend Core

Goal: Build the foundational processing system.

Implement:

rPPG processor (core signal extraction logic)
Chunk-based processing pipeline
Basic FastAPI app structure

Deliverables:

Modular backend architecture
Core processing logic working in isolation
Initial API skeleton (health check, basic endpoints) 


Prompt 4: 

Phase 2: Streaming & API Layer

Goal: Enable real-time data flow and full API functionality.

Implement:

Server-Sent Events (SSE) streaming
Chunk aggregation logic
Complete API endpoints for:
Processing
Streaming results

Validation:

Test full flow using curl (end-to-end)

Prompt 5: 

Phase 3: Frontend Application

Goal: Build a functional UI connected to the backend.

Implement:

React app using Vite
Core components (video input, results display, controls)
SSE integration for real-time updates
API connection layer

Deliverables:

Fully working frontend connected to backend
Real-time data rendering


Prompt 6: 

Phase 4: UI/UX & Polish

Goal: Improve usability and presentation.

Implement:

Charts for signal/metrics visualization
Performance summary table
Dark theme UI
Error handling and user feedback
Validation using test video input

Deliverables:

Clean, user-friendly interface
Robust handling of edge cases

Prompt 7:

Investigate the issue described in terminal.log, where only the CHROM method is being used while other methods are not functioning.Trace Full Execution Flow,Identify Failure Point, Analyze Why Fallback Happens, Treat Symptom as Clue, Provide Findings, While implementing, continuously validate assumptions against the original requirements. If any mismatch appears between implementation and expected behavior, pause and highlight it before proceeding.

