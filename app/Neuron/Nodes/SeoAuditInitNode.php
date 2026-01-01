<?php

declare(strict_types=1);

namespace App\Neuron\Nodes;

use App\Neuron\Agent\ContentAnalysisAgent;
use App\Neuron\Events\SeoAnalyseContentEvent;
use App\Services\CrawlerService;
use NeuronAI\Workflow\Node;
use NeuronAI\Workflow\StartEvent;
use NeuronAI\Workflow\WorkflowState;

class SeoAuditInitNode extends Node
{
    /**
     * Implement the Node's logic
     */
    public function __invoke(StartEvent $event, WorkflowState $state): SeoAnalyseContentEvent
    {
        logger('Starting SEO audit initialization', ['state' => $state->all()]);
        $url = $state->get('website_url');

        $crawlerService = app(CrawlerService::class);
        $result = $crawlerService->execute($url);

        $contentAnalysisAgent = ContentAnalysisAgent::make();
        $analysis = $contentAnalysisAgent->analyze($url, $result);

        $state->set('content_analysis', $analysis);

        return new SeoAnalyseContentEvent;
    }
}
