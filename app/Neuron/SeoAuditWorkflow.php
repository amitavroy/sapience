<?php

declare(strict_types=1);

namespace App\Neuron;

use App\Neuron\Nodes\SeoAnalyseContentNode;
use App\Neuron\Nodes\SeoAuditInitNode;
use NeuronAI\Workflow\Workflow;

class SeoAuditWorkflow extends Workflow
{
    protected function nodes(): array
    {
        return [
            new SeoAuditInitNode,
            new SeoAnalyseContentNode,
        ];
    }
}
