# Human-in-the-Loop Workflow Interruption Implementation Report

## Overview

This document describes the implementation of a human-in-the-loop interruption pattern in the Research Workflow using Neuron AI. The feature allows the workflow to pause and request user clarification before proceeding with search operations, enabling users to correct or refine their research queries.

## Problem Statement

When users initiate research with potentially ambiguous or incorrect queries (e.g., "PSR best costing practices" instead of "PSR best coding practices"), the system would generate search terms and perform searches based on the incorrect input. This led to irrelevant search results that didn't match the user's actual intent.

## Solution

We implemented a human-in-the-loop interruption pattern that:
1. Generates initial search terms from the user's query
2. Interrupts the workflow to show the generated search terms to the user
3. Allows users to provide clarification or corrections
4. Regenerates search terms based on the clarified input
5. Resumes the workflow with the corrected search terms

## Architecture

### Workflow Flow

```
InitialNode → GenerateSearchTermsNode → ContextClarificationNode → SearchNode → SummariseNode → ReportGenerateNode
                                                      ↓
                                              [INTERRUPTION]
                                                      ↓
                                            [User Provides Feedback]
                                                      ↓
                                            [Regenerate Search Terms]
                                                      ↓
                                              [RESUME]
```

### Component Overview

#### 1. ContextClarificationNode
**Location:** `app/Neuron/Nodes/ContextClarificationNode.php`

**Purpose:** Manages the interruption point and processes user feedback.

**Key Responsibilities:**
- Interrupts workflow after search terms are generated
- Displays generated search terms to the user
- Receives user feedback (clarification/correction)
- Extracts clarified topic from user input
- Regenerates search terms using the clarified topic
- Updates workflow state with new search terms

**Key Methods:**
- `getUserFeedback()` - Retrieves feedback from interruption or resume
- `extractClarifiedTopic()` - Extracts the actual query from phrases like "I meant X"
- `regenerateSearchTerms()` - Regenerates search terms with clarified topic
- `handleAdditionalContext()` - Processes additional context from user

#### 2. ResearchProcessJob
**Location:** `app/Jobs/ResearchProcessJob.php`

**Purpose:** Orchestrates workflow execution and handles interruptions.

**Key Responsibilities:**
- Creates workflow with persistence and unique ID
- Handles both starting new workflows and resuming interrupted workflows
- Catches `WorkflowInterrupt` exceptions
- Stores interruption data in the Research model
- Updates research status appropriately

**Key Methods:**
- `shouldResumeWorkflow()` - Determines if workflow should resume
- `resumeWorkflow()` - Resumes workflow with user feedback
- `startNewWorkflow()` - Starts a new workflow
- `handleWorkflowInterrupt()` - Handles interruption and stores data

#### 3. StartResearchController
**Location:** `app/Http/Controllers/StartResearchController.php`

**Purpose:** Handles HTTP requests for both starting and resuming research.

**Key Responsibilities:**
- Detects if request is for starting or resuming
- Extracts user feedback from request
- Stores feedback in Research model for job to pick up
- Dispatches ResearchProcessJob

**Key Methods:**
- `isResumingWorkflow()` - Checks if resuming based on status
- `extractFeedbackFromRequest()` - Extracts feedback from form data
- `storeFeedbackForResume()` - Stores feedback in interruption_data

#### 4. Database Schema Changes

**Migration:** `database/migrations/YYYY_MM_DD_HHMMSS_add_interruption_fields_to_research_table.php`

**New Fields:**
- `interruption_data` (JSON, nullable) - Stores interruption payload and user feedback
- `workflow_id` (string, nullable) - Unique identifier for workflow persistence

**Research Model Updates:**
- Added fields to `$fillable` array
- Added `interruption_data` cast as array

#### 5. Frontend Components

**Research Show Page:** `resources/js/pages/organisations/research/show.tsx`

**Features:**
- Displays interruption UI when status is `'awaiting_feedback'`
- Shows generated search terms to user
- Provides form for additional context input
- Submits feedback to resume workflow

**TypeScript Types:** Updated Research interface to include:
- `interruption_data` field
- `workflow_id` field
- `'awaiting_feedback'` status type

## How It Works

### Step-by-Step Flow

#### 1. Initial Workflow Start

```
User clicks "Start Research"
    ↓
StartResearchController receives request
    ↓
Dispatches ResearchProcessJob
    ↓
ResearchProcessJob creates workflow with:
  - WorkflowState (topic, user_id, etc.)
  - FilePersistence (storage/app/workflows)
  - Unique workflow_id (research_{id})
    ↓
Workflow executes:
  InitialNode → GenerateSearchTermsNode → ContextClarificationNode
    ↓
ContextClarificationNode calls interrupt()
    ↓
WorkflowInterrupt exception thrown
    ↓
ResearchProcessJob catches exception
    ↓
Stores interruption_data in Research model:
  {
    topic: "PSR best costing practices",
    search_terms: [...],
    question: "...",
    generated_at: "..."
  }
    ↓
Updates Research status to 'awaiting_feedback'
    ↓
Job completes (interruption is expected, not an error)
```

#### 2. User Provides Feedback

```
User views Research show page
    ↓
Page detects status === 'awaiting_feedback'
    ↓
Displays interruption UI:
  - Shows generated search terms
  - Shows question/prompt
  - Provides input field for additional context
    ↓
User enters: "I meant PSR best coding practices"
    ↓
User clicks "Resume Research"
    ↓
Form submits to StartResearchController
    ↓
Controller detects isResuming = true
    ↓
Extracts feedback from request:
  {
    additional_context: "I meant PSR best coding practices"
  }
    ↓
Stores feedback in Research.interruption_data:
  {
    ...existing_data,
    user_feedback: {
      additional_context: "I meant PSR best coding practices"
    }
  }
    ↓
Updates status to 'processing'
    ↓
Dispatches ResearchProcessJob again
```

#### 3. Workflow Resumption

```
ResearchProcessJob executes
    ↓
Detects shouldResume = true (workflow_id exists + status = 'processing' + user_feedback exists)
    ↓
Creates workflow with same workflow_id and persistence
    ↓
Extracts feedback from interruption_data['user_feedback']
    ↓
Calls workflow.wakeup(feedback)
    ↓
Workflow resumes from ContextClarificationNode
    ↓
ContextClarificationNode.consumeInterruptFeedback() returns feedback
    ↓
Node processes feedback:
  - Extracts clarified topic: "PSR best coding practices"
  - Regenerates search terms using SearchTermAgent
  - Updates state with new search_terms and topic
    ↓
Workflow continues:
  ContextClarificationNode → SearchNode → SummariseNode → ReportGenerateNode
    ↓
Workflow completes successfully
```

### Key Technical Details

#### Persistence

The workflow uses `FilePersistence` to save its state:
- **Location:** `storage/app/workflows/`
- **Purpose:** Preserves workflow state during interruption
- **Workflow ID Format:** `research_{research_id}`

When a workflow is interrupted:
1. Complete workflow state is saved to disk
2. Workflow ID is stored in Research model
3. On resume, workflow is loaded using the same ID

#### Feedback Processing

The `ContextClarificationNode` intelligently processes user feedback:

1. **Pattern Extraction:** Extracts the actual query from natural language:
   - "I meant X" → extracts X
   - "correct to X" → extracts X
   - "should be X" → extracts X
   - Otherwise uses the entire input as clarified topic

2. **Search Term Regeneration:**
   - Uses `SearchTermAgent` to generate new search terms
   - Uses the clarified topic (not original)
   - Updates both `topic` and `search_terms` in workflow state

3. **State Updates:**
   - `topic` → Updated to clarified version
   - `search_terms` → Regenerated based on clarified topic
   - `additional_context` → Stored for reference

#### Error Handling

- **WorkflowInterrupt:** Expected exception, handled gracefully
- **Workflow Errors:** Logged and research status set to 'failed'
- **Job Dispatch Errors:** Status reverted to 'awaiting_feedback' if resuming

## User Experience Flow

### From User's Perspective

1. **User creates research** with query: "PSR best costing practices"
2. **User starts research** → Workflow begins
3. **System generates search terms** → Shows terms related to "costing"
4. **System interrupts** → User sees interruption UI with generated terms
5. **User provides clarification** → Enters "I meant PSR best coding practices"
6. **User clicks "Resume Research"** → Workflow resumes
7. **System regenerates search terms** → Now based on "coding practices"
8. **System performs search** → Uses corrected search terms
9. **Research completes** → Results are relevant to coding practices

## Benefits

1. **Improved Accuracy:** Users can correct typos or clarify ambiguous queries
2. **Better Search Results:** Search terms are generated from corrected input
3. **User Control:** Users review and approve search terms before searching
4. **Seamless Experience:** Interruption is transparent to the user workflow
5. **State Preservation:** Complete workflow state is preserved during interruption

## Files Modified/Created

### Created Files
- `app/Neuron/Nodes/ContextClarificationNode.php`
- `app/Neuron/Events/ContextClarificationEvent.php`
- `database/migrations/YYYY_MM_DD_HHMMSS_add_interruption_fields_to_research_table.php`

### Modified Files
- `app/Neuron/ResearchWorkflow.php` - Added ContextClarificationNode
- `app/Neuron/Nodes/GenerateSearchTermsNode.php` - Returns ContextClarificationEvent
- `app/Jobs/ResearchProcessJob.php` - Added interruption handling and resume logic
- `app/Http/Controllers/StartResearchController.php` - Added resume handling
- `app/Http/Requests/StartResearchRequest.php` - Updated validation for resume
- `app/Models/Research.php` - Added new fields
- `routes/web.php` - Uses same route for start/resume
- `resources/js/types/index.d.ts` - Updated Research interface
- `resources/js/components/research-status-badge.tsx` - Added 'awaiting_feedback' status
- `resources/js/pages/organisations/research/show.tsx` - Added interruption UI

## Testing Considerations

When testing this feature:

1. **Test Interruption Flow:**
   - Start research → Verify interruption occurs
   - Check Research status is 'awaiting_feedback'
   - Verify interruption_data is stored

2. **Test Resume Flow:**
   - Provide additional context
   - Resume workflow
   - Verify search terms are regenerated
   - Verify search uses new terms

3. **Test Pattern Extraction:**
   - "I meant X" → Should extract X
   - "correct to X" → Should extract X
   - Direct input → Should use as-is

4. **Test Error Cases:**
   - Missing workflow_id on resume
   - Invalid feedback structure
   - Workflow resumption failures

## Future Enhancements

Potential improvements:
1. Support for multiple interruption points
2. Preview of search results before finalizing
3. Ability to edit individual search terms
4. History of clarifications made
5. AI-suggested clarifications based on generated terms

## Conclusion

The human-in-the-loop implementation successfully enables users to clarify and correct their research queries before search execution. The system gracefully handles interruptions, preserves state, and seamlessly resumes with user feedback, resulting in more accurate and relevant search results.

