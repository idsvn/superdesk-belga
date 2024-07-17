# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013, 2014 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

import datetime
import os
import unittest
from pytz import utc

from superdesk.etree import etree
from belga.io.feed_parsers.newsml_ctk_1_0_4 import NewsMLCTKFeedParser


class TestCase(unittest.TestCase):
    def setUp(self):
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.join(dirname, "../fixtures", "2405190001_CES_ENG.NML")
        provider = {"name": "Test"}
        with open(fixture, "rb") as f:
            self.item = NewsMLCTKFeedParser().parse(
                etree.fromstring(f.read()), provider
            )

    def test_headline(self):
        self.assertEqual(
            self.item.get("headline"),
            "Slovak PM Robert Fico, who is hospitalized after being shot by assassin, is out of danger of death, but recovery will take long time, hospital said.",
        )

    def test_dateline(self):
        self.assertEqual(self.item.get("dateline", {}).get("text"), "May 19, 2024")

    def test_slugline(self):
        self.assertEqual(self.item.get("slugline"), "")

    def test_byline(self):
        self.assertEqual(self.item.get("byline"), "")

    def test_language(self):
        self.assertEqual(self.item.get("language"), "en")

    def test_guid(self):
        self.assertEqual(
            self.item.get("guid"), "urn:newsml:ctk.cz:20245102:T2024051902729:1"
        )

    def test_coreitemvalues(self):
        self.assertEqual(self.item.get("type"), "text")
        self.assertEqual(self.item.get("urgency"), 3)
        self.assertEqual(self.item.get("version"), "1")
        self.assertEqual(
            self.item.get("versioncreated"),
            utc.localize(datetime.datetime(2024, 5, 19, 11, 54, 50)),
        )
        self.assertEqual(
            self.item.get("firstcreated"),
            utc.localize(datetime.datetime(2024, 5, 19, 11, 54, 50)),
        )
        self.assertEqual(self.item.get("pubstatus"), "usable")

    def test_subjects(self):
        self.assertEqual(len(self.item.get("subject")), 0)

    def test_keywords(self):
        self.assertEqual(len(self.item.get("keywords")), 5)
        self.assertIn("Slovakia", self.item.get("keywords"))
        self.assertIn("Fico", self.item.get("keywords"))
        self.assertIn("crime", self.item.get("keywords"))
        self.assertIn("health", self.item.get("keywords"))
        self.assertIn("HEADLINE", self.item.get("keywords"))

    def test_genre(self):
        self.assertEqual(len(self.item.get("genre")), 0)

    def test_content_is_text(self):
        self.assertIsInstance(self.item.get("body_html"), type(""))
        self.assertNotRegex(
            self.item.get("body_html"),
            '<DataContent xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
        )
        self.assertNotRegex(self.item.get("body_html"), "</DataContent>")
        self.assertNotRegex(
            self.item.get("body_html"),
            '<body xmlns="http://newsml.ctk.cz/ns/ctkxhtml.xsd">',
        )
        self.assertNotRegex(self.item.get("body_html"), "</body>")
