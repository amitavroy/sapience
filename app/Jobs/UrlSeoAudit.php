<?php

namespace App\Jobs;

use App\Neuron\SeoAuditWorkflow;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use NeuronAI\Workflow\WorkflowState;

class UrlSeoAudit implements ShouldQueue
{
    use Queueable;

    /**
     * Create a new job instance.
     */
    public function __construct(
        public string $websiteUrl,
        public int $auditId
    ) {}

    /**
     * Execute the job.
     */
    public function handle(): void
    {
        $state = new WorkflowState([
            'website_url' => $this->websiteUrl,
            'audit_id' => $this->auditId,
        ]);

        $workflow = SeoAuditWorkflow::make(state: $state);

        $handler = $workflow->start();

        $result = $handler->getResult();

        logger('SEO audit result', ['result' => $result]);
    }
}
