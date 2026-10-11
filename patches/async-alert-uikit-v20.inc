/*
 * Applesauce V20 asynchronous guest-alert bridge.
 * Copyright 2026 touchHLE contributors.
 * Distributed under SDL's zlib license (see SDL_uikitmessagebox.m).
 *
 * Only UIKit-owned strings/state cross the presentation boundary. Native
 * handlers record a button index; the guest polls it on its own run loop.
 * There is no nested modal wait and no synthetic user selection.
 */
#import <UIKit/UIKit.h>
#include <stdint.h>

@interface TouchHLEAlertControllerV20 : UIViewController
@property(nonatomic) UIInterfaceOrientationMask orientationMask;
@end
@implementation TouchHLEAlertControllerV20
- (UIInterfaceOrientationMask)supportedInterfaceOrientations
{
    return self.orientationMask;
}
- (BOOL)shouldAutorotate { return NO; }
@end

@interface TouchHLEAlertStateV20 : NSObject
@property(nonatomic) uint64_t token;
@property(nonatomic) NSInteger selectedIndex;
@property(nonatomic, copy) NSString *title;
@property(nonatomic, copy) NSString *message;
@property(nonatomic, copy) NSArray<NSString *> *buttonTitles;
@property(nonatomic, weak) UIWindow *parentWindow;
@property(nonatomic, weak) UIWindow *previousKeyWindow;
@property(nonatomic, strong) UIWindow *window;
@property(nonatomic, strong) UIAlertController *controller;
@end
@implementation TouchHLEAlertStateV20
@end

static NSMutableDictionary<NSNumber *, TouchHLEAlertStateV20 *> *touchHLEAlertsV20;
static NSMutableArray<NSNumber *> *touchHLEAlertQueueV20;
static uint64_t touchHLEActiveAlertV20;
static uint64_t touchHLENextAlertV20 = 1;

static BOOL TouchHLE_AlertOnMainThreadV20(void)
{
    if ([NSThread isMainThread]) return YES;
    NSLog(@"[ALERT NATIVE v20] Refused off-main-thread alert operation");
    return NO;
}

static void TouchHLE_CloseAlertWindowV20(TouchHLEAlertStateV20 *state)
{
    BOOL wasKeyWindow = state.window.isKeyWindow;
    [state.window.rootViewController dismissViewControllerAnimated:NO completion:nil];
    state.window.hidden = YES;
    state.window.rootViewController = nil;
    state.controller = nil;
    state.window = nil;
    UIWindow *previous = state.previousKeyWindow;
    if (wasKeyWindow && previous && !previous.hidden) [previous makeKeyWindow];
}

/* Shared by the actual UIAlertAction handler and the simulator regression. */
static void TouchHLE_RecordAlertSelectionV20(TouchHLEAlertStateV20 *state,
                                            NSInteger index)
{
    if (!state || touchHLEAlertsV20[@(state.token)] != state ||
        state.token != touchHLEActiveAlertV20 || state.selectedIndex != -1 ||
        index < 0 || index >= (NSInteger)state.buttonTitles.count) return;
    state.selectedIndex = index;
    NSLog(@"[ALERT NATIVE v20] Button %ld selected for token %llu",
          (long)index, (unsigned long long)state.token);
}

static void TouchHLE_PresentNextAlertV20(void)
{
    if (touchHLEActiveAlertV20) return;
    while (touchHLEAlertQueueV20.count) {
        NSNumber *key = touchHLEAlertQueueV20.firstObject;
        [touchHLEAlertQueueV20 removeObjectAtIndex:0];
        TouchHLEAlertStateV20 *state = touchHLEAlertsV20[key];
        if (!state) continue;
        UIWindowScene *scene = state.parentWindow.windowScene;
        if (!scene) {
            for (UIScene *candidate in UIApplication.sharedApplication.connectedScenes) {
                if ([candidate isKindOfClass:[UIWindowScene class]] &&
                    candidate.activationState == UISceneActivationStateForegroundActive) {
                    scene = (UIWindowScene *)candidate;
                    break;
                }
            }
        }
        if (!scene) {
            state.selectedIndex = -2;
            NSLog(@"[ALERT NATIVE v20] No active window scene for token %llu",
                  (unsigned long long)state.token);
            continue;
        }
        for (UIWindow *candidate in scene.windows) {
            if (candidate.isKeyWindow) { state.previousKeyWindow = candidate; break; }
        }
        if (!state.previousKeyWindow) state.previousKeyWindow = state.parentWindow;
        TouchHLEAlertControllerV20 *root = [TouchHLEAlertControllerV20 new];
        root.orientationMask = UIInterfaceOrientationIsLandscape(scene.interfaceOrientation)
            ? UIInterfaceOrientationMaskLandscape : UIInterfaceOrientationMaskPortrait;
        UIWindow *window = [[UIWindow alloc] initWithWindowScene:scene];
        window.frame = scene.coordinateSpace.bounds;
        window.backgroundColor = UIColor.clearColor;
        window.windowLevel = UIWindowLevelAlert + 1;
        window.rootViewController = root;
        window.accessibilityIdentifier = @"touchHLE.asyncAlert.v20";
        state.window = window;
        UIAlertController *alert = [UIAlertController
            alertControllerWithTitle:state.title message:state.message
            preferredStyle:UIAlertControllerStyleAlert];
        state.controller = alert;
        __weak TouchHLEAlertStateV20 *weakState = state;
        for (NSUInteger index = 0; index < state.buttonTitles.count; index++) {
            /* Capture the index by value, never pointers into SDL/guest storage. */
            UIAlertAction *action = [UIAlertAction actionWithTitle:state.buttonTitles[index]
                style:UIAlertActionStyleDefault handler:^(UIAlertAction *unused) {
                    (void)unused;
                    TouchHLE_RecordAlertSelectionV20(weakState, (NSInteger)index);
                }];
            [alert addAction:action];
        }
        touchHLEActiveAlertV20 = state.token;
        [window makeKeyAndVisible];
        /* No animated presentation/rotation transaction while the core owns
         * the main thread. Ordinary SDL event turns keep UIKit responsive. */
        [root presentViewController:alert animated:NO completion:nil];
        NSLog(@"[ALERT NATIVE v20] Presented token %llu with %lu buttons above game controls",
              (unsigned long long)state.token, (unsigned long)state.buttonTitles.count);
        return;
    }
}

static uint64_t TouchHLE_BeginAsyncAlertV20(UIWindow *parent,
    const char *title, const char *message, const char *const *buttons, int count)
{
    if (!TouchHLE_AlertOnMainThreadV20() || !buttons || count < 1 || count > 256)
        return 0;
    if (!touchHLEAlertsV20) {
        touchHLEAlertsV20 = [NSMutableDictionary new];
        touchHLEAlertQueueV20 = [NSMutableArray new];
    }
    if (!touchHLENextAlertV20) return 0; /* Never reuse a stale token. */
    TouchHLEAlertStateV20 *state = [TouchHLEAlertStateV20 new];
    state.token = touchHLENextAlertV20++;
    state.selectedIndex = -1;
    state.parentWindow = parent;
    state.title = title ? ([NSString stringWithUTF8String:title] ?: @"") : @"";
    state.message = message ? ([NSString stringWithUTF8String:message] ?: @"") : @"";
    NSMutableArray<NSString *> *titles = [NSMutableArray arrayWithCapacity:count];
    for (int index = 0; index < count; index++) {
        NSString *text = buttons[index] ? [NSString stringWithUTF8String:buttons[index]] : nil;
        [titles addObject:text ?: @""];
    }
    state.buttonTitles = titles;
    touchHLEAlertsV20[@(state.token)] = state;
    [touchHLEAlertQueueV20 addObject:@(state.token)];
    TouchHLE_PresentNextAlertV20();
    return state.token;
}

static void TouchHLE_DismissAsyncAlertV20(uint64_t token)
{
    if (!TouchHLE_AlertOnMainThreadV20()) return;
    TouchHLEAlertStateV20 *state = touchHLEAlertsV20[@(token)];
    if (!state) return;
    [touchHLEAlertQueueV20 removeObject:@(token)];
    if (touchHLEActiveAlertV20 == token) {
        TouchHLE_CloseAlertWindowV20(state);
        touchHLEActiveAlertV20 = 0;
    }
    [touchHLEAlertsV20 removeObjectForKey:@(token)];
    TouchHLE_PresentNextAlertV20();
}

/* -1 = pending; -2 = absent/presentation failed; >=0 = a genuine button. */
static int TouchHLE_PollAsyncAlertV20(uint64_t token)
{
    if (!TouchHLE_AlertOnMainThreadV20()) return -2;
    TouchHLEAlertStateV20 *state = touchHLEAlertsV20[@(token)];
    if (!state) return -2;
    int result = (int)state.selectedIndex;
    if (result != -1) TouchHLE_DismissAsyncAlertV20(token);
    return result;
}

static void TouchHLE_ResetAsyncAlertsV20(void)
{
    if (!TouchHLE_AlertOnMainThreadV20()) return;
    TouchHLEAlertStateV20 *active = touchHLEAlertsV20[@(touchHLEActiveAlertV20)];
    if (active) TouchHLE_CloseAlertWindowV20(active);
    touchHLEActiveAlertV20 = 0;
    [touchHLEAlertQueueV20 removeAllObjects];
    [touchHLEAlertsV20 removeAllObjects];
}
