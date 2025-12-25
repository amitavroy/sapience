<?php

declare(strict_types=1);

namespace App\Neuron;

use App\Neuron\Nodes\InitialNode;
use App\Neuron\Nodes\ReportGenerateNode;
use App\Neuron\Nodes\SearchNode;
use App\Neuron\Nodes\SummariseNode;
use NeuronAI\Workflow\Workflow;

class ResearchWorkflow extends Workflow
{
    protected function nodes(): array
    {
        return [
            new InitialNode,
            new SearchNode,
            new SummariseNode,
            new ReportGenerateNode,
        ];
    }
}
