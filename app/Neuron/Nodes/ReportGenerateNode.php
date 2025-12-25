<?php

declare(strict_types=1);

namespace App\Neuron\Nodes;

use App\Models\Research;
use App\Neuron\Agent\ReportAgent;
use App\Neuron\Events\ReportGenerateEvent;
use NeuronAI\Chat\Messages\UserMessage;
use NeuronAI\Workflow\Node;
use NeuronAI\Workflow\StopEvent;
use NeuronAI\Workflow\WorkflowState;

class ReportGenerateNode extends Node
{
    /**
     * Implement the Node's logic
     */
    public function __invoke(ReportGenerateEvent $event, WorkflowState $state): StopEvent
    {
        logger('Generating the report');
        $researchId = $state->get('research_id');
        $research = Research::find($researchId);
        $researchLinks = $research->researchLinks()->get();

        $summaryContent = collect();
        $researchLinks->each(function ($researchLink) use ($summaryContent) {
            $summaryContent->push($researchLink->summary);
        });

        $completeSummary = implode("\n\n==========================\n\n", $summaryContent->toArray());

        $report = ReportAgent::make()->chat(new UserMessage($completeSummary));
        $research->report = $report->getContent();
        $research->save();

        return new StopEvent;
    }
}
