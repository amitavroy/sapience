<?php

declare(strict_types=1);

namespace App\Neuron\Nodes;

use App\Models\Research;
use App\Neuron\Agent\SummariseAgent;
use App\Neuron\Events\ReportGenerateEvent;
use App\Neuron\Events\SummariseEvent;
use App\Services\CrawlerService;
use NeuronAI\Chat\Messages\UserMessage;
use NeuronAI\Workflow\Node;
use NeuronAI\Workflow\WorkflowState;

class SummariseNode extends Node
{
    /**
     * Implement the Node's logic
     */
    public function __invoke(SummariseEvent $event, WorkflowState $state): ReportGenerateEvent
    {
        logger('Summarising the content');

        if (config('sapience.workflow_fake')) {
            logger('Using fake workflow: SummariseNode');

            return new ReportGenerateEvent;
        }

        $researchId = $state->get('research_id');
        $research = Research::find($researchId);

        $resultsLimit = config('services.search.results', 5);
        $researchLinks = $resultsLimit === 0
            ? $research->researchLinks
            : $research->researchLinks->take($resultsLimit);

        $researchLinks->each(function ($researchLink): void {
            $crawlService = app(CrawlerService::class);
            $result = $crawlService->execute($researchLink->url);

            // Skip if crawl was unsuccessful or content is empty
            if (! $result->success || empty($result->content)) {
                $researchLink->status = 'failed';
                $researchLink->save();

                return;
            }

            $content = $result->content;

            $response = SummariseAgent::make()->chat(new UserMessage($content));
            $summary = $response->getContent();

            $researchLink->summary = $summary;
            $researchLink->status = 'completed';
            $researchLink->save();
        });

        $research->status = 'completed';
        $research->save();

        return new ReportGenerateEvent;
    }
}
