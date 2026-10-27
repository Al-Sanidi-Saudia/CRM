// Campaign form: shows the platform campaign lookup and the auto number of each
// selected social media channel, and clears the lookups that no longer apply.
// sanidi_socialmediachannel is multi-select, so more than one channel can show.
// The channel numbers (MC-2026-01-M) are set by the AutoNumbering plug-in and are
// kept when a channel is unticked; they are only hidden.
// Register Sanidi.Campaign.onLoad on form load (pass execution context);
// it wires the sanidi_socialmediachannel change handler itself.
var Sanidi = window.Sanidi = window.Sanidi || {};
Sanidi.Campaign = (function () {
    "use strict";

    var CHANNEL_FIELD = "sanidi_socialmediachannel";

    // sanidi_socialmediachannel option value -> platform campaign lookup and channel number
    var CHANNELS = [
        { value: 1, lookup: "sanidi_metacampaign", number: "sanidi_metanumber" },           // Meta
        { value: 5, lookup: "sanidi_snapcampaign", number: "sanidi_snapnumber" },           // Snap
        { value: 4, lookup: "sanidi_tiktokcampaign", number: "sanidi_tiktoknumber" },       // TikTok
        { value: 6, lookup: "sanidi_googleadscampaign", number: "sanidi_googleadsnumber" }  // Google Ads
    ];

    function selectedChannels(formContext) {
        var attr = formContext.getAttribute(CHANNEL_FIELD);
        var value = attr ? attr.getValue() : null;
        if (value === null || value === undefined) return [];
        return Array.isArray(value) ? value : [value];
    }

    function apply(formContext, clearHidden) {
        var selected = selectedChannels(formContext);
        CHANNELS.forEach(function (channel) {
            var visible = selected.indexOf(channel.value) !== -1;
            var lookupControl = formContext.getControl(channel.lookup);
            if (lookupControl) lookupControl.setVisible(visible);
            var numberControl = formContext.getControl(channel.number);
            if (numberControl) numberControl.setVisible(visible);
            if (!visible && clearHidden) {
                var attr = formContext.getAttribute(channel.lookup);
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
