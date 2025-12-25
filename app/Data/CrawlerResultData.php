<?php

namespace App\Data;

use Spatie\LaravelData\Data;

class CrawlerResultData extends Data
{
    public function __construct(
        public bool $success,
        public string $markup,
        /** @var array<string, string> */
        public array $meta,
        public string $title,
        /** @var array<string> */
        public array $headings,
        public string $content,
    ) {}
}
