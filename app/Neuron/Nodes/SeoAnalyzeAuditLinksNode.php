<?php

declare(strict_types=1);

namespace App\Neuron\Nodes;

use App\Models\Audit;
use App\Models\AuditLink;
use App\Neuron\Agent\SeoCompetitorAnalysisAgent;
use App\Neuron\Events\SeoAnalyzeAuditLinksEvent;
use App\Neuron\Events\SeoGenerateReportEvent;
use NeuronAI\Chat\Messages\UserMessage;
use NeuronAI\Workflow\Node;
use NeuronAI\Workflow\WorkflowState;

class SeoAnalyzeAuditLinksNode extends Node
{
    /**
     * Implement the Node's logic
     */
    public function __invoke(SeoAnalyzeAuditLinksEvent $event, WorkflowState $state): SeoGenerateReportEvent
    {
        logger('Analyzing audit links for SEO insights');

        if (config('sapience.workflow_fake')) {
            logger('Using fake workflow: SeoAnalyzeAuditLinksNode');

            return new SeoGenerateReportEvent;
        }

        $auditId = $state->get('audit_id');
        $audit = Audit::find($auditId);

        if (! $audit) {
            logger('Audit not found', ['audit_id' => $auditId]);

            return new SeoGenerateReportEvent;
        }

        $auditLinks = AuditLink::where('audit_id', $auditId)
            ->where('status', 'pending')
            ->get();

        if ($auditLinks->isEmpty()) {
            logger('No pending audit links found', ['audit_id' => $auditId]);

            return new SeoGenerateReportEvent;
        }

        $seoCompetitorAnalysisAgent = SeoCompetitorAnalysisAgent::make();

        $auditLinks->each(function ($auditLink) use ($seoCompetitorAnalysisAgent): void {
            logger('Analyzing link', ['url' => $auditLink->url]);

            try {
                $content = $auditLink->content ?? '';
                $title = $auditLink->title ?? 'No title';
                $url = $auditLink->url;

                if (empty($content)) {
                    logger('No content available for analysis', ['url' => $url]);
                    $auditLink->status = 'failed';
                    $auditLink->save();

                    return;
                }

                $analysisPrompt = $this->buildAnalysisPrompt($url, $title, $content);

                $response = $seoCompetitorAnalysisAgent->chat(new UserMessage($analysisPrompt));
                $summary = $response->getContent();

                $auditLink->summary = $summary;
                $auditLink->status = 'completed';
                $auditLink->save();

                logger('Analysis completed', ['url' => $url]);

                sleep(5); // add a wait of 2 seconds to not hit rate limits
            } catch (\Exception $e) {
                logger('Error analyzing link', [
                    'url' => $auditLink->url,
                    'error' => $e->getMessage(),
                ]);
                $auditLink->status = 'failed';
                $auditLink->save();
            }
        });

        logger('All audit links analyzed', [
            'audit_id' => $auditId,
            'total' => $auditLinks->count(),
        ]);

        return new SeoGenerateReportEvent;
    }

    private function buildAnalysisPrompt(string $url, string $title, string $content): string
    {
        $truncatedContent = mb_substr($content, 0, 8000);

        return <<<PROMPT
Analyze the following website content for SEO strengths and weaknesses.

**URL:** {$url}
**Title:** {$title}
**Content:**
{$truncatedContent}

Provide a detailed SEO analysis focusing on what this website is doing well and what could be improved.
PROMPT;
    }
}
