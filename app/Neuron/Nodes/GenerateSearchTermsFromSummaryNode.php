<?php

declare(strict_types=1);

namespace App\Neuron\Nodes;

use App\Models\Audit;
use App\Neuron\Agent\SummarySearchTermAgent;
use App\Neuron\Events\GenerateSearchTermsFromSummaryEvent;
use App\Neuron\Events\SeoSearchSimilarWebsiteEvent;
use NeuronAI\Chat\Messages\UserMessage;
use NeuronAI\Workflow\Node;
use NeuronAI\Workflow\WorkflowState;

class GenerateSearchTermsFromSummaryNode extends Node
{
    /**
     * Implement the Node's logic
     */
    public function __invoke(GenerateSearchTermsFromSummaryEvent $event, WorkflowState $state): SeoSearchSimilarWebsiteEvent
    {
        logger('Generating search terms from summary');

        if (config('sapience.workflow_fake')) {
            logger('Using fake workflow: GenerateSearchTermsFromSummaryNode');

            return new SeoSearchSimilarWebsiteEvent;
        }

        $auditId = $state->get('audit_id');
        $audit = Audit::find($auditId);

        if (! $audit) {
            logger('Audit not found', ['audit_id' => $auditId]);

            return new SeoSearchSimilarWebsiteEvent;
        }

        $summary = $audit->analysis;

        if (empty($summary)) {
            logger('Summary is empty for audit', ['audit_id' => $auditId]);

            return new SeoSearchSimilarWebsiteEvent;
        }

        $summarySearchTermAgent = SummarySearchTermAgent::make();
        $response = $summarySearchTermAgent->chat(new UserMessage($summary));

        $content = $response->getContent();
        $result = json_decode($content, true);

        if (! isset($result['search_terms'])) {
            logger('Invalid response from SummarySearchTermAgent', ['response' => $content]);

            return new SeoSearchSimilarWebsiteEvent;
        }

        $audit->search_terms = $result['search_terms'];
        $audit->save();

        logger('Search terms generated and saved', ['count' => count($result['search_terms'])]);

        return new SeoSearchSimilarWebsiteEvent;
    }
}
