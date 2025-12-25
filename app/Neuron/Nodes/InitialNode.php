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

        $researchId = $state->get('research_id');
        $research = Research::findOrFail($researchId);

        $research->update([
            'status' => 'processing',
        ]);

        return new SearchEvent;
    }
}
