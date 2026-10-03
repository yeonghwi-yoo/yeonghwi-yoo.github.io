---
title: "전체 글"
layout: single
permalink: /posts/
author_profile: true
description: "퀀트 노트의 모든 글을 시리즈별로 모았습니다. 퀀트 투자 입문 20편, 퀀트 실전 10편, 그리고 그 밖의 실험과 정리 글입니다."
---

퀀트 노트의 글을 시리즈별로 모았습니다. 처음이라면 입문 시리즈를 위에서부터, 필요한 주제만 찾는다면 각 시리즈의 정리 글부터 보시면 됩니다.

{% assign all = site.posts | reverse %}

## 퀀트 투자 입문

백테스트가 무엇이고 어디서 틀리는지, 팩터와 자산 배분은 데이터로 보면 어떤지 다룹니다. [20편 정리 글](/posts/quant-intro-series-index/)에 한 줄 요약이 있습니다.

<ol>
{%- for post in all -%}
{%- if post.series == "intro" and post.url != "/posts/quant-intro-series-index/" %}
  <li><a href="{{ post.url | relative_url }}">{{ post.title }}</a> <small>{{ post.date | date: "%Y-%m-%d" }}</small></li>
{%- endif -%}
{%- endfor %}
</ol>

## 퀀트 실전

한국 종목 데이터로 스크리닝하고, 그 결과를 검증하고, 비중과 크기를 정하고, 세금과 자동매매까지 실제 계좌로 옮기는 과정입니다. [10편 정리 글](/posts/quant-practice-series-index/)에 한 줄 요약이 있습니다.

<ol>
{%- for post in all -%}
{%- if post.series == "practice" and post.url != "/posts/quant-practice-series-index/" %}
  <li><a href="{{ post.url | relative_url }}">{{ post.title }}</a> <small>{{ post.date | date: "%Y-%m-%d" }}</small></li>
{%- endif -%}
{%- endfor %}
</ol>

## 그 밖의 글

<ul>
{%- for post in site.posts -%}
{%- unless post.series == "intro" or post.series == "practice" %}
  <li><a href="{{ post.url | relative_url }}">{{ post.title }}</a> <small>{{ post.date | date: "%Y-%m-%d" }}</small></li>
{%- endunless -%}
{%- endfor %}
</ul>
