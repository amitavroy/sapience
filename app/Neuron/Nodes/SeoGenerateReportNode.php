<?php

declare(strict_types=1);

namespace App\Neuron\Nodes;

use App\Enums\AuditStatus;
use App\Models\Audit;
use App\Models\AuditLink;
use App\Neuron\Agent\SeoReportAgent;
use App\Neuron\Events\SeoGenerateReportEvent;
use NeuronAI\Chat\Messages\UserMessage;
use NeuronAI\Workflow\Node;
use NeuronAI\Workflow\StopEvent;
use NeuronAI\Workflow\WorkflowState;

class SeoGenerateReportNode extends Node
{
    /**
     * Implement the Node's logic
     */
    public function __invoke(SeoGenerateReportEvent $event, WorkflowState $state): StopEvent
    {
        logger('Generating SEO report');

        if (config('sapience.workflow_fake')) {
            logger('Using fake workflow: SeoGenerateReportNode');

            return new StopEvent;
        }

        $auditId = $state->get('audit_id');
        $audit = Audit::find($auditId);

        if (! $audit) {
            logger('Audit not found', ['audit_id' => $auditId]);

            return new StopEvent;
        }

        $auditLinks = AuditLink::where('audit_id', $auditId)
            ->where('status', 'completed')
            ->whereNotNull('summary')
            ->get();

        if ($auditLinks->isEmpty()) {
            logger('No completed audit links with summaries found', ['audit_id' => $auditId]);
            $audit->status = AuditStatus::Failed;
            $audit->save();

            return new StopEvent;
        }

        $summaryContent = collect();
        $auditLinks->each(function ($auditLink) use ($summaryContent): void {
            $linkInfo = "**URL:** {$auditLink->url}\n";
            $linkInfo .= "**Search Term:** {$auditLink->search_term}\n";
            if ($auditLink->title) {
                $linkInfo .= "**Title:** {$auditLink->title}\n";
            }
            $linkInfo .= "\n**SEO Analysis:**\n{$auditLink->summary}";
            $summaryContent->push($linkInfo);
        });

        $completeSummary = implode("\n\n==========================\n\n", $summaryContent->toArray());

        $prompt = "**Target Website URL:** {$audit->website_url}\n\n";

        if (! empty($audit->analysis)) {
            $prompt .= "**Initial Website Analysis:**\n\n{$audit->analysis}\n\n";
            $prompt .= "==========================\n\n";
        }

        $prompt .= "**Competitor SEO Analysis Summaries:**\n\n{$completeSummary}";

        logger('Generating comprehensive SEO report', [
            'audit_id' => $auditId,
            'links_count' => $auditLinks->count(),
        ]);

        try {
            $seoReportAgent = SeoReportAgent::make();
            $report = $seoReportAgent->chat(new UserMessage($prompt));
            $reportContent = $report->getContent();

            $audit->report = $reportContent;
            $audit->status = AuditStatus::Completed;
            $audit->save();

            logger('SEO report generated and saved successfully', ['audit_id' => $auditId]);
        } catch (\Exception $e) {
            logger('Error generating SEO report', [
                'audit_id' => $auditId,
                'error' => $e->getMessage(),
            ]);
            $audit->status = AuditStatus::Failed;
            $audit->save();

            return new StopEvent;
        }

        return new StopEvent;
    }
}
