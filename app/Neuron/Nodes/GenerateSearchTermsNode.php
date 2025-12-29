<?php

declare(strict_types=1);

namespace App\Neuron\Nodes;

use App\Neuron\Agent\SearchTermAgent;
use App\Neuron\Events\ContextClarificationEvent;
use App\Neuron\Events\GenerateSearchKeywordsEvent;
use NeuronAI\Chat\Messages\UserMessage;
use NeuronAI\Workflow\Node;
use NeuronAI\Workflow\WorkflowState;

class GenerateSearchTermsNode extends Node
{
    /**
     * Implement the Node's logic
     */
    public function __invoke(GenerateSearchKeywordsEvent $event, WorkflowState $state): ContextClarificationEvent
    {
        $topic = $state->get('topic');
        logger('Generating search terms');

        $topic = $state->get('topic');

        $searchTermAgent = SearchTermAgent::make();
        $response = $searchTermAgent->chat(new UserMessage($topic));

        $content = $response->getContent();
        $result = json_decode($content, true);
        $state->set('search_terms', $result['alternative_queries']);

        if (config('sapience.workflow_fake')) {
            logger('Using fake workflow: GenerateSearchTermsNode');

            return new ContextClarificationEvent;
        }

        return new ContextClarificationEvent;
    }
}
