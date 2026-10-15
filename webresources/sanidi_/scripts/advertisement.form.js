// Advertisement form (main and quick create): shows the platform advertisement
// lookup that matches sanidi_channel, clears the others, and restricts it to
// ads under the platform campaign linked on the parent sanidi_campaign.
// If the parent campaign has no platform campaign for that channel, the lookup
// returns no results.
// Register Sanidi.Advertisement.onLoad on form load (pass execution context);
// it wires the sanidi_channel and sanidi_campaign change handlers itself.
var Sanidi = window.Sanidi = window.Sanidi || {};
Sanidi.Advertisement = (function () {
    "use strict";

    var CHANNEL_FIELD = "sanidi_channel";
    var CAMPAIGN_FIELD = "sanidi_campaign";

    // sanidi_channel option values -> platform advertisement lookup and how to
    // reach the platform campaign from an ad: either a lookup on the ad that
    // points at the platform campaign (via), or a parent record (ad squad /
    // ad group) that points at it.
    var PLATFORMS = [
        {
            field: "sanidi_metaadvertisement", entity: "sanidi_metaadvertisement",
            channels: [1, 2],                       // Facebook, Instagram
            campaignField: "sanidi_metacampaign",   // on sanidi_campaign
            via: "sanidi_metacampaignid"
        },
        {
            field: "sanidi_snapadvertisement", entity: "sanidi_snapadvertisement",
            channels: [5],                          // Snapchat
            campaignField: "sanidi_snapcampaign",
            parentField: "sanidi_snapadsquad",
            parentTable: "sanidi_snapadsquad",
            parentCampaignField: "sanidi_snapcampaign"
        },
        {
            field: "sanidi_googleadsadvertisement", entity: "sanidi_googleadsadvertisement",
            channels: [6, 7],                       // Google, YouTube
            campaignField: "sanidi_googleadscampaign",
            parentField: "sanidi_googleadsadgroup",
            parentTable: "sanidi_googleadsadgroup",
            parentCampaignField: "sanidi_googleadscampaign"
        }
    ];

    function platformFor(channel) {
        for (var i = 0; i < PLATFORMS.length; i++) {
            if (PLATFORMS[i].channels.indexOf(channel) !== -1) return PLATFORMS[i];
        }
        return null;
    }

    function lookupId(formContext, field) {
        var attr = formContext.getAttribute(field);
        var value = attr ? attr.getValue() : null;
        return value && value.length ? value[0].id.replace(/[{}]/g, "").toLowerCase() : null;
    }

    function noResultsFilter(platform) {
        return "<filter type='and'><condition attribute='" + platform.entity + "id' operator='null' /></filter>";
    }

    function inFilter(attribute, ids) {
        var values = ids.map(function (id) { return "<value>" + id + "</value>"; }).join("");
        return "<filter type='and'><condition attribute='" + attribute + "' operator='in'>" + values + "</condition></filter>";
    }

    function buildFilter(platform, campaignId) {
        if (!campaignId) return Promise.resolve(noResultsFilter(platform));
        return Xrm.WebApi.retrieveRecord("sanidi_campaign", campaignId,
            "?$select=_" + platform.campaignField + "_value"
        ).then(function (campaign) {
            var platformCampaignId = campaign["_" + platform.campaignField + "_value"];
            if (!platformCampaignId) return noResultsFilter(platform);
            if (platform.via) return inFilter(platform.via, [platformCampaignId]);
            return Xrm.WebApi.retrieveMultipleRecords(platform.parentTable,
                "?$select=" + platform.parentTable + "id&$filter=_" + platform.parentCampaignField +
                "_value eq " + platformCampaignId
            ).then(function (result) {
                var ids = result.entities.map(function (e) { return e[platform.parentTable + "id"]; });
                return ids.length ? inFilter(platform.parentField, ids) : noResultsFilter(platform);
            });
        });
    }

    function clear(formContext, field) {
        var attr = formContext.getAttribute(field);
        if (attr && attr.getValue() !== null) {
            attr.setValue(null);
            attr.fireOnChange();
        }
    }

    // One state object per opened form, so a quick create opened on top of a
    // main form (or the next record opened in the same window) keeps its own filters.
    function bind(formContext) {
        var filters = {};
        var seq = 0;

        function refresh(clearHidden, clearSelected) {
            var channelAttr = formContext.getAttribute(CHANNEL_FIELD);
            var active = platformFor(channelAttr ? channelAttr.getValue() : null);

            PLATFORMS.forEach(function (platform) {
                var visible = platform === active;
                var control = formContext.getControl(platform.field);
                if (control) control.setVisible(visible);
                if (!visible) {
                    if (clearHidden) clear(formContext, platform.field);
                    filters[platform.field] = null;
                }
            });

            if (!active) return Promise.resolve();
            if (clearSelected) clear(formContext, active.field);

            var current = ++seq;
            filters[active.field] = noResultsFilter(active);
            return buildFilter(active, lookupId(formContext, CAMPAIGN_FIELD)).then(function (filter) {
                if (current === seq) filters[active.field] = filter;
            }, function (error) {
                console.error("Sanidi.Advertisement: could not build " + active.field + " filter", error);
            });
        }

        PLATFORMS.forEach(function (platform) {
            var control = formContext.getControl(platform.field);
            if (!control) return;
            control.addPreSearch(function () {
                control.addCustomFilter(filters[platform.field] || noResultsFilter(platform), platform.entity);
            });
        });

        var channelAttr = formContext.getAttribute(CHANNEL_FIELD);
        if (channelAttr) channelAttr.addOnChange(function () { refresh(true, false); });
        var campaignAttr = formContext.getAttribute(CAMPAIGN_FIELD);
        if (campaignAttr) campaignAttr.addOnChange(function () { refresh(true, true); });

        return refresh(false, false);
    }

    return {
        onLoad: function (executionContext) {
            return bind(executionContext.getFormContext());
        }
    };
})();
