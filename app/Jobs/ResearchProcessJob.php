<?php

namespace App\Jobs;

use App\Models\Organisation;
use App\Models\User;
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
        public User $user,
        public Organisation $organisation,
        public string $topic
    ) {
        //
    }

    /**
     * Execute the job.
     */
    public function handle(): void
    {
        $state = new WorkflowState([
            'topic' => $this->topic,
            'user_id' => $this->user->id,
            'organisation_id' => $this->organisation->id,
        ]);

        ResearchWorkflow::make(state: $state)->start();
    }
}
