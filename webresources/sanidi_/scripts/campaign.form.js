// Campaign form: shows the platform campaign lookup(s) that match the
// selected social media channel(s) and clears the ones that no longer apply.
// sanidi_socialmediachannel is multi-select, so more than one lookup can show.
// Register Sanidi.Campaign.onLoad on form load (pass execution context);
// it wires the sanidi_socialmediachannel change handler itself.
var Sanidi = window.Sanidi = window.Sanidi || {};
Sanidi.Campaign = (function () {
    "use strict";

    var CHANNEL_FIELD = "sanidi_socialmediachannel";

    // sanidi_socialmediachannel option values -> platform campaign lookup
    var LOOKUPS = [
        { field: "sanidi_metacampaign", channels: [1, 2] },      // Facebook, Instagram
        { field: "sanidi_snapcampaign", channels: [5] },         // Snapchat
        { field: "sanidi_googleadscampaign", channels: [6, 7] }, // Google, YouTube
        { field: "sanidi_tiktokcampaign", channels: [4] }        // TikTok
    ];

    function selectedChannels(formContext) {
        var attr = formContext.getAttribute(CHANNEL_FIELD);
        var value = attr ? attr.getValue() : null;
        if (value === null || value === undefined) return [];
        return Array.isArray(value) ? value : [value];
    }

    function apply(formContext, clearHidden) {
        var selected = selectedChannels(formContext);
        LOOKUPS.forEach(function (lookup) {
            var visible = lookup.channels.some(function (c) { return selected.indexOf(c) !== -1; });
            var control = formContext.getControl(lookup.field);
            if (control) control.setVisible(visible);
            if (!visible && clearHidden) {
                var attr = formContext.getAttribute(lookup.field);
                if (attr && attr.getValue() !== null) {
                    attr.setValue(null);
                    attr.fireOnChange();
                }
            }
        });
    }

    return {
        onLoad: function (executionContext) {
            var formContext = executionContext.getFormContext();
            var channelAttr = formContext.getAttribute(CHANNEL_FIELD);
            if (channelAttr) channelAttr.addOnChange(function () { apply(formContext, true); });
            apply(formContext, false);
        }
    };
})();
