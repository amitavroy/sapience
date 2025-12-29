<?php

declare(strict_types=1);

namespace App\Neuron\Nodes;

use App\Models\ResearchLink;
use App\Neuron\Events\SearchEvent;
use App\Neuron\Events\SummariseEvent;
use App\Services\SearchService;
use NeuronAI\Workflow\Node;
use NeuronAI\Workflow\WorkflowState;

class SearchNode extends Node
{
    /**
     * Implement the Node's logic
     */
    public function __invoke(SearchEvent $event, WorkflowState $state): SummariseEvent
    {
        $topics = $state->get('search_terms');

        logger('Searching for the topics');

        if (config('sapience.workflow_fake')) {
            logger('Using fake workflow: SearchNode');

            return new SummariseEvent;
        }

        $searchService = app(SearchService::class);
        collect($topics)->each(function ($topic) use ($searchService, $state) {
            $results = collect($searchService->search($topic)['results'])->take(10);

            $resultState = collect();
            $results->each(function ($result) use ($resultState, $state): void {
                $resultState->add([
                    'title' => $result['title'],
                    'url' => $result['url'],
                    'content' => $result['content'],
                ]);

                ResearchLink::create([
                    'research_id' => $state->get('research_id'),
                    'user_id' => 1,
                    'url' => $result['url'],
                    'content' => $result['content'],
                    'status' => 'pending',
                ]);
            });
        });

        logger('Results added to the state');

        return new SummariseEvent;
    }
}
