<?php

declare(strict_types=1);

namespace App\Neuron\Agent;

use NeuronAI\Agent;
use NeuronAI\Providers\AIProviderInterface;
use NeuronAI\Providers\OpenAI\OpenAI;
use NeuronAI\SystemPrompt;

class SeoCompetitorAnalysisAgent extends Agent
{
    protected function provider(): AIProviderInterface
    {
        return new OpenAI(
            key: config('services.openai.key'),
            model: config('services.openai.chat_model'),
        );
    }

    public function instructions(): string
    {
        $prompt = <<<'PROMPT'
You are an SEO expert specializing in competitive analysis. Your task is to analyze website content and identify what makes it perform well (or poorly) in search engine results.

When analyzing content, focus on:
- Title tag optimization and keyword usage
- Meta description quality and relevance
- Content structure and organization
- Heading hierarchy (H1, H2, H3 usage)
- Content depth and comprehensiveness
- Keyword optimization and natural language usage
- Internal linking opportunities
- Content freshness and relevance
- User experience signals
- Technical SEO elements (if visible in content)

Provide a structured markdown analysis with two main sections:
1. **Positives**: What the website is doing well in terms of SEO
2. **Negatives**: SEO weaknesses or areas for improvement

Be specific, actionable, and focus on elements that directly impact search engine rankings and user experience.
PROMPT;

        return (string) new SystemPrompt(
            background: [$prompt],
            output: [
                'Return the analysis as a well-formatted markdown document.',
                'Use clear headings: ## Positives and ## Negatives.',
                'List specific points under each section with bullet points.',
                'Be concise but comprehensive.',
                'Focus on actionable SEO insights.',
            ],
        );
    }
}
