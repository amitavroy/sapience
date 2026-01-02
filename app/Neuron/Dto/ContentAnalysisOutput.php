<?php

declare(strict_types=1);

namespace App\Neuron\Dto;

use NeuronAI\StructuredOutput\SchemaProperty;
use NeuronAI\StructuredOutput\Validation\Rules\NotBlank;

class ContentAnalysisOutput
{
    // Classification
    #[SchemaProperty(description: 'The type of content page', required: true)]
    #[NotBlank]
    public string $content_type;

    #[SchemaProperty(description: 'The search intent this content targets', required: true)]
    #[NotBlank]
    public string $search_intent;

    #[SchemaProperty(description: 'The industry or vertical this content belongs to (e.g., healthcare technology, e-commerce fashion, B2B SaaS)', required: true)]
    #[NotBlank]
    public string $industry_vertical;

    #[SchemaProperty(description: 'Who is this content for? Describe the target audience', required: true)]
    #[NotBlank]
    public string $target_audience;

    // Topic Analysis
    #[SchemaProperty(description: 'The main subject in 3-5 words', required: true)]
    #[NotBlank]
    public string $primary_topic;

    #[SchemaProperty(description: 'The single most important keyword/phrase to rank for', required: true)]
    #[NotBlank]
    public string $primary_keyword;

    #[SchemaProperty(description: '3-5 supporting keywords that complement the primary keyword', required: true)]
    public array $secondary_keywords;

    #[SchemaProperty(description: 'Named entities, brands, concepts mentioned in the content', required: true)]
    public array $entities;

    #[SchemaProperty(description: 'What questions does this content answer?', required: true)]
    public array $questions_addressed;

    // Content Assessment
    #[SchemaProperty(description: 'The depth of content coverage', required: true)]
    #[NotBlank]
    public string $content_depth;

    #[SchemaProperty(description: '2-4 things this page does well', required: true)]
    public array $content_strengths;

    #[SchemaProperty(description: '2-4 obvious gaps or issues', required: true)]
    public array $content_weaknesses;

    #[SchemaProperty(description: 'What perspective or value does this bring? null if generic', required: false)]
    public ?string $unique_angle;

    // SEO Assessment
    #[SchemaProperty(description: 'Quality rating of the title tag', required: true)]
    #[NotBlank]
    public string $title_tag_quality;

    #[SchemaProperty(description: 'Array of issues with the title tag, empty if none', required: true)]
    public array $title_tag_issues;

    #[SchemaProperty(description: 'Quality rating of the meta description', required: true)]
    #[NotBlank]
    public string $meta_description_quality;

    #[SchemaProperty(description: 'Array of issues with the meta description, empty if none', required: true)]
    public array $meta_description_issues;

    #[SchemaProperty(description: 'Quality rating of the heading structure', required: true)]
    #[NotBlank]
    public string $heading_structure_quality;

    #[SchemaProperty(description: 'Array of issues with the heading structure, empty if none', required: true)]
    public array $heading_issues;

    #[SchemaProperty(description: 'Array of schema types that should be added', required: true)]
    public array $schema_opportunities;

    // Competitor Search Strategy
    #[SchemaProperty(description: '3-5 search queries to find competing content. These should be what a user would type to find this type of content. Vary between head terms and long-tail', required: true)]
    public array $search_queries;

    #[SchemaProperty(description: 'Criteria a page MUST meet to be a valid competitor', required: true)]
    public array $competitor_must_have;

    #[SchemaProperty(description: 'Signals that indicate a strong competitor', required: true)]
    public array $competitor_good_signals;

    #[SchemaProperty(description: 'Signals that indicate NOT a competitor (e.g., forums, social media)', required: true)]
    public array $competitor_exclude_signals;

    #[SchemaProperty(description: 'List of 4-6 specific things to compare against competitors. These should be relevant to THIS content type (e.g., for a product page: pricing visibility, reviews, specs depth; for a blog post: topic coverage, examples provided, actionable advice)', required: true)]
    public array $comparison_dimensions;
}
