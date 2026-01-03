<?php

namespace App\Jobs;

use App\Models\Research;
use App\Models\WorkflowInterrupt;
use App\Neuron\Persistence\DatabasePersistence;
use App\Neuron\ResearchWorkflow;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use NeuronAI\Workflow\WorkflowInterrupt as WorkflowInterruptException;
use NeuronAI\Workflow\WorkflowState;

class ResearchProcessJob implements ShouldQueue
{
    use Queueable;

    /**
     * Create a new job instance.
     */
    public function __construct(
        public int $researchId
    ) {
        //
    }

    /**
     * Execute the job.
     */
    public function handle(): void
    {
        logger('Starting research process job', ['research_id' => $this->researchId]);

        try {
            $research = Research::findOrFail($this->researchId);
            $state = $this->createWorkflowState($research);
            $workflowId = $this->getWorkflowId($research);
            $persistence = $this->createPersistence();

            if ($this->shouldResumeWorkflow($research)) {
                $handler = $this->resumeWorkflow($research, $state, $persistence, $workflowId);
            } else {
                $handler = $this->startNewWorkflow($research, $state, $persistence, $workflowId);
            }

            $this->executeWorkflow($handler);
        } catch (WorkflowInterruptException $interrupt) {
            $this->handleWorkflowInterrupt($interrupt);
        } catch (\Throwable $e) {
            $this->handleWorkflowError($e);
        }

        logger('Research process job completed successfully', ['research_id' => $this->researchId]);
    }

    /**
     * Create workflow state from research model
     */
    private function createWorkflowState(Research $research): WorkflowState
    {
        return new WorkflowState([
            'topic' => $research->query,
            'user_id' => $research->user_id,
            'organisation_id' => $research->organisation_id,
            'research_id' => $research->id,
        ]);
    }

    /**
     * Get or generate workflow ID for the research
     */
    private function getWorkflowId(Research $research): string
    {
        return $research->workflow_id ?? "research_{$research->id}";
    }

    /**
     * Create and configure persistence for workflow
     */
    private function createPersistence(): DatabasePersistence
    {
        return new DatabasePersistence(WorkflowInterrupt::class);
    }

    /**
     * Check if workflow should be resumed instead of started
     */
    private function shouldResumeWorkflow(Research $research): bool
    {
        return $research->workflow_id
            && $research->status === 'processing'
            && isset($research->interruption_data['user_feedback']);
    }

    /**
     * Resume an existing workflow with user feedback
     */
    private function resumeWorkflow(Research $research, WorkflowState $state, DatabasePersistence $persistence, string $workflowId)
    {
        logger('Resuming existing workflow', [
            'research_id' => $this->researchId,
            'workflow_id' => $workflowId,
        ]);

        $workflow = new ResearchWorkflow($state, $persistence, $workflowId);
        $feedback = $this->extractFeedbackFromResearch($research);

        logger('Waking up workflow with feedback', [
            'research_id' => $this->researchId,
            'feedback' => $feedback,
        ]);

        return $workflow->wakeup($feedback);
    }

    /**
     * Extract user feedback from research interruption data
     */
    private function extractFeedbackFromResearch(Research $research): array
    {
        $feedback = $research->interruption_data['user_feedback'] ?? [];

        $research->update(['interruption_data' => null]);

        return $feedback;
    }

    /**
     * Start a new workflow
     */
    private function startNewWorkflow(Research $research, WorkflowState $state, DatabasePersistence $persistence, string $workflowId)
    {
        logger('Creating new workflow', [
            'research_id' => $this->researchId,
            'workflow_id' => $workflowId,
        ]);

        $workflow = new ResearchWorkflow($state, $persistence, $workflowId);

        if (! $research->workflow_id) {
            $research->update(['workflow_id' => $workflowId]);
        }

        logger('Starting workflow execution', ['research_id' => $this->researchId]);

        return $workflow->start();
    }

    /**
     * Execute workflow and wait for result
     */
    private function executeWorkflow($handler): void
    {
        logger('Waiting for workflow result', ['research_id' => $this->researchId]);
        $result = $handler->getResult();

        logger('Workflow execution completed', [
            'research_id' => $this->researchId,
            'result' => $result,
        ]);
    }

    /**
     * Handle workflow interruption - store interruption data and update status
     */
    private function handleWorkflowInterrupt(WorkflowInterruptException $interrupt): void
    {
        logger('Workflow interrupted', [
            'research_id' => $this->researchId,
            'interrupt_data' => $interrupt->getData(),
        ]);

        $research = Research::findOrFail($this->researchId);
        $workflowId = $this->getWorkflowId($research);

        $research->update([
            'interruption_data' => $interrupt->getData(),
            'status' => 'awaiting_feedback',
            'workflow_id' => $workflowId,
        ]);

        logger('Research status updated to awaiting_feedback', ['research_id' => $this->researchId]);
    }

    /**
     * Handle workflow errors - log and update research status to failed
     */
    private function handleWorkflowError(\Throwable $e): void
    {
        logger()->error('Error in research process job', [
            'research_id' => $this->researchId,
            'error' => $e->getMessage(),
            'trace' => $e->getTraceAsString(),
            'file' => $e->getFile(),
            'line' => $e->getLine(),
        ]);

        $this->updateResearchStatusToFailed();

        throw $e;
    }

    /**
     * Update research status to failed
     */
    private function updateResearchStatusToFailed(): void
    {
        try {
            $research = Research::find($this->researchId);
            if ($research) {
                $research->update(['status' => 'failed']);
            }
        } catch (\Throwable $updateException) {
            logger()->error('Failed to update research status', [
                'error' => $updateException->getMessage(),
            ]);
        }
    }
}
