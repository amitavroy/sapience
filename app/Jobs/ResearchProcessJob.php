<?php

namespace App\Jobs;

use App\Models\Research;
use App\Neuron\ResearchWorkflow;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
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

            $state = new WorkflowState([
                'topic' => $research->query,
                'user_id' => $research->user_id,
                'organisation_id' => $research->organisation_id,
                'research_id' => $research->id,
            ]);

            logger('Creating workflow', ['research_id' => $this->researchId]);
            $workflow = ResearchWorkflow::make(state: $state);

            logger('Starting workflow execution', ['research_id' => $this->researchId]);
            $handler = $workflow->start();

            logger('Waiting for workflow result', ['research_id' => $this->researchId]);
            $result = $handler->getResult();

            logger('Workflow execution completed', [
                'research_id' => $this->researchId,
                'result' => $result,
            ]);
        } catch (\Throwable $e) {
            logger()->error('Error in research process job', [
                'research_id' => $this->researchId,
                'error' => $e->getMessage(),
                'trace' => $e->getTraceAsString(),
                'file' => $e->getFile(),
                'line' => $e->getLine(),
            ]);

            // Update research status to failed
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

            throw $e;
        }

        logger('Research process job completed successfully', ['research_id' => $this->researchId]);
    }
}
