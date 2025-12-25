<?php

declare(strict_types=1);

namespace App\Neuron\Nodes;

use App\Models\Research;
use App\Neuron\Events\SearchEvent;
use NeuronAI\Workflow\Node;
use NeuronAI\Workflow\StartEvent;
use NeuronAI\Workflow\WorkflowState;

class InitialNode extends Node
{
    /**
     * Implement the Node's logic
     */
    public function __invoke(StartEvent $event, WorkflowState $state): SearchEvent
    {
        logger('Starting the workflow');

        $research = Research::create([
            'user_id' => $state->get('user_id'),
            'organisation_id' => $state->get('organisation_id'),
            'query' => $state->get('topic'),
            'status' => 'pending',
        ]);

        $state->set('research_id', $research->id);

        return new SearchEvent;
    }
}
