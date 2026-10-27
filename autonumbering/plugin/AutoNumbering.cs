using System;
using System.Collections.Generic;
using System.Linq;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Query;

namespace Sanidi.Marketing.Plugins
{
    // Auto numbering for marketing campaigns and advertisements:
    //   campaign                 MC-2026-01       (prefix, year, counter that restarts every year)
    //   campaign channel number  MC-2026-01-M     (one read-only column per channel, kept when the channel is unticked)
    //   advertisement            MC-2026-01-M-01  (counter per channel within the campaign)
    // The prefix and the channel codes come from the single sanidi_autonumbersetting row, which also holds the
    // current year and the last campaign number. The last advertisement number per channel is kept on the campaign.
    //
    // Registered synchronously on PreOperation (see autonumbering/deploy.py):
    //   Create sanidi_campaign; Update sanidi_campaign (filtered on sanidi_socialmediachannel);
    //   Create sanidi_advertisement.
    // Numbers are taken while holding a write lock on the settings row, so two saves at the same moment never get
    // the same number; the lock is released when the save's transaction ends. Reads and writes run as SYSTEM so
    // users need no privileges on the settings table.
    public class AutoNumbering : IPlugin
    {
        const string Settings = "sanidi_autonumbersetting";
        const string Campaign = "sanidi_campaign";
        const string Advertisement = "sanidi_advertisement";
        const string Name = "sanidi_name";
        const string CampaignChannels = "sanidi_socialmediachannel";
        const string AdChannel = "sanidi_channel";
        const string AdCampaign = "sanidi_campaign";

        // Year boundaries follow Saudi time (UTC+3, no daylight saving).
        static readonly TimeSpan SaudiOffset = TimeSpan.FromHours(3);

        sealed class Channel
        {
            public int Value;            // sanidi_socialmediachannel option
            public string Label;
            public string CodeColumn;    // on sanidi_autonumbersetting
            public string DefaultCode;
            public string NumberColumn;  // on sanidi_campaign: MC-2026-01-M
            public string CounterColumn; // on sanidi_campaign: last advertisement number for this channel
        }

        static readonly Channel[] Channels =
        {
            new Channel { Value = 1, Label = "Meta", CodeColumn = "sanidi_metacode", DefaultCode = "M",
                          NumberColumn = "sanidi_metanumber", CounterColumn = "sanidi_lastmetaadnumber" },
            new Channel { Value = 5, Label = "Snap", CodeColumn = "sanidi_snapcode", DefaultCode = "S",
                          NumberColumn = "sanidi_snapnumber", CounterColumn = "sanidi_lastsnapadnumber" },
            new Channel { Value = 4, Label = "TikTok", CodeColumn = "sanidi_tiktokcode", DefaultCode = "T",
                          NumberColumn = "sanidi_tiktoknumber", CounterColumn = "sanidi_lasttiktokadnumber" },
            new Channel { Value = 6, Label = "Google Ads", CodeColumn = "sanidi_googleadscode", DefaultCode = "G",
                          NumberColumn = "sanidi_googleadsnumber", CounterColumn = "sanidi_lastgoogleadsadnumber" },
        };

        public void Execute(IServiceProvider serviceProvider)
        {
            var context = (IPluginExecutionContext)serviceProvider.GetService(typeof(IPluginExecutionContext));
            var factory = (IOrganizationServiceFactory)serviceProvider.GetService(typeof(IOrganizationServiceFactory));
            var tracing = (ITracingService)serviceProvider.GetService(typeof(ITracingService));
            if (!(context.InputParameters.TryGetValue("Target", out var t) && t is Entity target))
                return;
            var service = factory.CreateOrganizationService(null);

            if (target.LogicalName == Campaign && context.MessageName == "Create")
                NumberCampaign(service, target, tracing);
            else if (target.LogicalName == Campaign && context.MessageName == "Update")
                AddChannelNumbers(service, target, tracing);
            else if (target.LogicalName == Advertisement && context.MessageName == "Create")
                NumberAdvertisement(service, target, tracing);
        }

        static void NumberCampaign(IOrganizationService service, Entity target, ITracingService tracing)
        {
            var settings = LockSettings(service);
            var year = DateTime.UtcNow.Add(SaudiOffset).Year.ToString();
            var last = settings.GetAttributeValue<string>("sanidi_currentyear") == year
                ? settings.GetAttributeValue<int?>("sanidi_lastcampaignnumber") ?? 0
                : 0;
            var next = last + 1;
            var number = $"{Text(settings, "sanidi_campaignprefix", "MC")}-{year}-{next:D2}";
            target[Name] = number;

            foreach (var channel in Selected(target.GetAttributeValue<OptionSetValueCollection>(CampaignChannels)))
                target[channel.NumberColumn] = $"{number}-{Code(settings, channel)}";

            service.Update(new Entity(Settings, settings.Id)
            {
                ["sanidi_currentyear"] = year,
                ["sanidi_lastcampaignnumber"] = next,
            });
            tracing.Trace($"Campaign number {number}");
        }

        // A channel ticked later gets its number then; a number is never changed or cleared afterwards.
        static void AddChannelNumbers(IOrganizationService service, Entity target, ITracingService tracing)
        {
            if (!target.Contains(CampaignChannels))
                return;
            var channels = Selected(target.GetAttributeValue<OptionSetValueCollection>(CampaignChannels)).ToList();
            if (channels.Count == 0)
                return;
            var campaign = service.Retrieve(Campaign, target.Id,
                new ColumnSet(new[] { Name }.Concat(channels.Select(c => c.NumberColumn)).ToArray()));
            var number = campaign.GetAttributeValue<string>(Name);
            if (string.IsNullOrWhiteSpace(number))
                return;
            var settings = ReadSettings(service);
            foreach (var channel in channels)
            {
                if (!string.IsNullOrEmpty(campaign.GetAttributeValue<string>(channel.NumberColumn)))
                    continue;
                target[channel.NumberColumn] = $"{number}-{Code(settings, channel)}";
                tracing.Trace($"{channel.Label} number {target[channel.NumberColumn]}");
            }
        }

        static void NumberAdvertisement(IOrganizationService service, Entity target, ITracingService tracing)
        {
            var campaignRef = target.GetAttributeValue<EntityReference>(AdCampaign);
            var channelValue = target.GetAttributeValue<OptionSetValue>(AdChannel);
            if (campaignRef == null || channelValue == null)
                throw new InvalidPluginExecutionException(
                    "Select the campaign and the channel before saving the advertisement.");
            var channel = Channels.FirstOrDefault(c => c.Value == channelValue.Value)
                ?? throw new InvalidPluginExecutionException(
                    "Select one of the channels Meta, Snap, TikTok or Google Ads.");

            var settings = LockSettings(service);
            var campaign = service.Retrieve(Campaign, campaignRef.Id,
                new ColumnSet(Name, CampaignChannels, channel.NumberColumn, channel.CounterColumn));
            var campaignName = campaign.GetAttributeValue<string>(Name);
            var campaignChannels = campaign.GetAttributeValue<OptionSetValueCollection>(CampaignChannels);
            if (campaignChannels == null || campaignChannels.All(o => o.Value != channel.Value))
                throw new InvalidPluginExecutionException(
                    $"The campaign {campaignName} doesn't include the {channel.Label} channel. " +
                    $"Add {channel.Label} to the campaign's channels first.");

            var update = new Entity(Campaign, campaign.Id);
            var channelNumber = campaign.GetAttributeValue<string>(channel.NumberColumn);
            if (string.IsNullOrEmpty(channelNumber))
            {
                // Campaigns from before auto numbering get their channel number on first use.
                channelNumber = $"{campaignName}-{Code(settings, channel)}";
                update[channel.NumberColumn] = channelNumber;
            }
            var next = (campaign.GetAttributeValue<int?>(channel.CounterColumn) ?? 0) + 1;
            update[channel.CounterColumn] = next;
            target[Name] = $"{channelNumber}-{next:D2}";
            service.Update(update);
            tracing.Trace($"Advertisement number {target[Name]}");
        }

        static IEnumerable<Channel> Selected(OptionSetValueCollection values)
        {
            if (values == null)
                return Enumerable.Empty<Channel>();
            return Channels.Where(c => values.Any(o => o.Value == c.Value));
        }

        static string Code(Entity settings, Channel channel) => Text(settings, channel.CodeColumn, channel.DefaultCode);

        static string Text(Entity settings, string column, string fallback)
        {
            var value = settings.GetAttributeValue<string>(column);
            return string.IsNullOrWhiteSpace(value) ? fallback : value.Trim();
        }

        static readonly string[] SettingsColumns =
            new[] { "sanidi_campaignprefix", "sanidi_currentyear", "sanidi_lastcampaignnumber" }
                .Concat(Channels.Select(c => c.CodeColumn)).ToArray();

        static Entity ReadSettings(IOrganizationService service)
        {
            var query = new QueryExpression(Settings) { ColumnSet = new ColumnSet(SettingsColumns), TopCount = 1 };
            query.Criteria.AddCondition("statecode", ConditionOperator.Equal, 0);
            query.AddOrder("createdon", OrderType.Ascending);
            var row = service.RetrieveMultiple(query).Entities.FirstOrDefault();
            if (row != null)
                return row;
            // First use in an environment: start from the default codes.
            row = new Entity(Settings)
            {
                [Name] = "Marketing Auto Numbering",
                ["sanidi_campaignprefix"] = "MC",
            };
            foreach (var channel in Channels)
                row[channel.CodeColumn] = channel.DefaultCode;
            row.Id = service.Create(row);
            return row;
        }

        // Writing to the row first makes every other numbering save wait here until this transaction ends;
        // the values are read only after the lock is held.
        static Entity LockSettings(IOrganizationService service)
        {
            var id = ReadSettings(service).Id;
            service.Update(new Entity(Settings, id) { ["sanidi_lastnumberissuedon"] = DateTime.UtcNow });
            return service.Retrieve(Settings, id, new ColumnSet(SettingsColumns));
        }
    }
}
