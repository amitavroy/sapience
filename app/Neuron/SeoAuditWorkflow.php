<?php

declare(strict_types=1);

namespace App\Neuron;

use App\Neuron\Nodes\GenerateSearchTermsFromSummaryNode;
use App\Neuron\Nodes\SeoAnalyseContentNode;
use App\Neuron\Nodes\SeoAnalyzeAuditLinksNode;
use App\Neuron\Nodes\SeoAuditInitNode;
use App\Neuron\Nodes\SeoGenerateReportNode;
use App\Neuron\Nodes\SeoSearchSimilarWebsiteNode;
use NeuronAI\Workflow\Workflow;

class SeoAuditWorkflow extends Workflow
{
    protected function nodes(): array
    {
        return [
            new SeoAuditInitNode,
            new SeoAnalyseContentNode,
            new GenerateSearchTermsFromSummaryNode,
            new SeoSearchSimilarWebsiteNode,
            new SeoAnalyzeAuditLinksNode,
            new SeoGenerateReportNode,
        ];
    }
}
