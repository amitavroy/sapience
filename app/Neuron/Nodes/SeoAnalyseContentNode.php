<?php

declare(strict_types=1);

namespace App\Neuron\Nodes;

use App\Models\Audit;
use App\Neuron\Agent\ContentAnalysisSummariserAgent;
use App\Neuron\Events\SeoAnalyseContentEvent;
use NeuronAI\Workflow\Node;
use NeuronAI\Workflow\StopEvent;
use NeuronAI\Workflow\WorkflowState;

class SeoAnalyseContentNode extends Node
{
    /**
     * Implement the Node's logic
     */
    public function __invoke(SeoAnalyseContentEvent $event, WorkflowState $state): StopEvent
    {
        logger('Analysing the content');

        $content_analysis = $state->get('content_analysis');

        $audit_id = $state->get('audit_id');
        $audit = Audit::find($audit_id);

        $contentAnalysisSummariserAgent = ContentAnalysisSummariserAgent::make();
        $summary = $contentAnalysisSummariserAgent->summarize($content_analysis);

        $state->set('summary', $summary);

        logger('===============================================');
        logger('Summary', ['summary' => $summary]);
        $audit->analysis = $summary;
        $audit->status = 'summarised';
        $audit->save();

        return new StopEvent;
    }
}
