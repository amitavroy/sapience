<?php

declare(strict_types=1);

namespace App\Neuron\Agent;

use App\Data\CrawlerResultData;
use App\Neuron\Dto\ContentAnalysisOutput;
use App\Services\UtilService;
use NeuronAI\Agent;
use NeuronAI\Chat\Messages\UserMessage;
use NeuronAI\Providers\AIProviderInterface;
use NeuronAI\Providers\OpenAI\OpenAI;
use NeuronAI\SystemPrompt;

class ContentAnalysisAgent extends Agent
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
        return (string) new SystemPrompt(
            background: [
                'You are an SEO and content analysis expert. Analyze webpage data and provide structured assessments.',
            ],
        );
    }

    public function analyze(string $url, CrawlerResultData $crawlerResult): ContentAnalysisOutput
    {
        $prompt = $this->buildPrompt($url, $crawlerResult);

        return $this->structured(
            new UserMessage($prompt),
            ContentAnalysisOutput::class
        );
    }

    private function buildPrompt(string $url, CrawlerResultData $crawlerResult): string
    {
        $metaDescription = $crawlerResult->meta['description'] ?? $crawlerResult->meta['og:description'] ?? '';
        $schemaTypes = UtilService::extractSchemaTypes($crawlerResult->markup);
        $headingsList = UtilService::formatHeadingsHierarchically($crawlerResult->headings);
        $truncatedContent = UtilService::truncateContent($crawlerResult->content);

        return <<<PROMPT
You are an SEO and content analysis expert. Analyze the following webpage data and provide a structured assessment.

## Input Data

**URL:** {$url}

**Title Tag:** {$crawlerResult->title}

**Meta Description:** {$metaDescription}

**Schema Markup Present:** {$schemaTypes}

**Headings Structure:**
{$headingsList}

**Main Content:**
{$truncatedContent}

---

## Your Task

Analyze this page and provide a comprehensive assessment covering:

1. **Classification**: Determine the content type (blog_post, product_page, landing_page, documentation, news_article, comparison_page, listicle, homepage, or other), search intent (informational, transactional, commercial_investigation, navigational), industry vertical, and target audience.

2. **Topic Analysis**: Identify the primary topic (3-5 words), primary keyword, 3-5 secondary keywords, named entities/brands/concepts mentioned, and questions the content addresses.

3. **Content Assessment**: Evaluate content depth (shallow, moderate, comprehensive), list 2-4 strengths, 2-4 weaknesses, and identify any unique angle or perspective (null if generic).

4. **SEO Assessment**: Rate the quality of title tag, meta description, and heading structure (poor, adequate, good, excellent). List any issues found (empty arrays if none). Suggest schema opportunities.

5. **Competitor Search Strategy**: Generate 3-5 realistic search queries users would type (mix of direct keywords, questions, and long-tail). Define competitor criteria (must_have, good_signals, exclude_signals). List 4-6 comparison dimensions relevant to THIS content type.

## Guidelines

1. **Be specific to the content type.** A product page and a blog post have different success criteria. Your `comparison_dimensions` should reflect what matters for THIS type of content.

2. **Search queries should be realistic.** Generate queries that actual users would type, not SEO jargon. Include a mix of:
   - Direct keyword search
   - Question-based search
   - Long-tail variant

3. **Be critical but fair.** Don't invent problems that don't exist, but don't be generous either. This analysis drives improvement recommendations.

4. **For competitor_criteria**, think about what makes a page a TRUE competitor for the same search intent, not just topically related content.
PROMPT;
    }
}
